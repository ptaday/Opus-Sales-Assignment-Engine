"""Unit tests for seed service (CSV helpers; generate_companies mocked)."""
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.services import seed_service


class TestFormatCell:
    def test_none_or_empty_returns_empty_string(self):
        assert seed_service._format_cell(None, "x") == ""
        assert seed_service._format_cell("", "x") == ""

    def test_string_stripped(self):
        assert seed_service._format_cell("  a  ", "x") == "a"

    def test_non_string_returned_unchanged(self):
        assert seed_service._format_cell(42, "x") == 42


class TestLoadExistingKeys:
    def test_missing_file_returns_empty_set(self, tmp_path):
        out = seed_service.load_existing_keys(tmp_path / "missing.csv", "company_name")
        assert out == set()

    def test_returns_keys_from_csv(self, tmp_path):
        csv_path = tmp_path / "out.csv"
        csv_path.write_text("company_name,industry\nAcme,Retail\nBeta,Restaurants\n")
        out = seed_service.load_existing_keys(csv_path, "company_name")
        assert "acme" in out
        assert "beta" in out


class TestAppendToCsv:
    def test_creates_file_and_writes_header(self, tmp_path, sample_seed_config):
        csv_path = tmp_path / "seed.csv"
        sample_seed_config["output_path"] = csv_path
        companies = [
            {"company_name": "A", "location_count": 5, "industry": "Retail"},
        ]
        added, skipped = seed_service.append_to_csv(companies, csv_path, sample_seed_config)
        assert added == 1
        assert skipped == 0
        content = csv_path.read_text()
        assert "company_name" in content
        assert "A" in content

    def test_skips_duplicates_by_key(self, tmp_path, sample_seed_config):
        csv_path = tmp_path / "seed.csv"
        sample_seed_config["output_path"] = csv_path
        companies = [
            {"company_name": "A", "location_count": 5, "industry": "Retail"},
            {"company_name": "A", "location_count": 10, "industry": "Restaurants"},
        ]
        added, skipped = seed_service.append_to_csv(companies, csv_path, sample_seed_config)
        assert added == 1
        assert skipped == 1
        assert csv_path.read_text().count("A") == 1


class TestGenerateCompanies:
    def test_returns_parsed_companies_when_mock_returns_json(self, sample_seed_config):
        raw = json.dumps([
            {"company_name": "C1", "location_count": 5, "industry": "Retail"},
            {"company_name": "C2", "location_count": 10, "industry": "Restaurants"},
        ])
        mock_message = MagicMock()
        mock_message.content = [MagicMock()]
        mock_message.content[0].text = raw
        with patch.object(seed_service, "anthropic", MagicMock()):
            with patch("src.services.seed_service._anthropic_rate_limit"):
                with patch("src.services.seed_service.anthropic.Anthropic") as MockClient:
                    MockClient.return_value.messages.create.return_value = mock_message
                    out = seed_service.generate_companies("fake-key", sample_seed_config)
        assert len(out) == 2
        assert out[0]["company_name"] == "C1"
        assert out[1]["industry"] == "Restaurants"

    def test_raises_on_missing_field(self, sample_seed_config):
        raw = json.dumps([{"company_name": "C1", "location_count": 5}])  # missing industry
        mock_message = MagicMock()
        mock_message.content = [MagicMock()]
        mock_message.content[0].text = raw
        with patch.object(seed_service, "anthropic", MagicMock()):
            with patch("src.services.seed_service._anthropic_rate_limit"):
                with patch("src.services.seed_service.anthropic.Anthropic") as MockClient:
                    MockClient.return_value.messages.create.return_value = mock_message
                    with pytest.raises(ValueError, match="Missing field"):
                        seed_service.generate_companies("fake-key", sample_seed_config)

    def test_strips_code_fence_from_response(self, sample_seed_config):
        raw = "```json\n[{\"company_name\":\"X\",\"location_count\":1,\"industry\":\"R\"}]\n```"
        mock_message = MagicMock()
        mock_message.content = [MagicMock()]
        mock_message.content[0].text = raw
        with patch.object(seed_service, "anthropic", MagicMock()):
            with patch("src.services.seed_service._anthropic_rate_limit"):
                with patch("src.services.seed_service.anthropic.Anthropic") as MockClient:
                    MockClient.return_value.messages.create.return_value = mock_message
                    out = seed_service.generate_companies("fake-key", sample_seed_config)
        assert len(out) == 1
        assert out[0]["company_name"] == "X"
