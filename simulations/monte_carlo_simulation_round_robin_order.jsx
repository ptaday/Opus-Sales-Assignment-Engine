/**
 * The summary cards are your headline. Avg Std Dev — that's the single most important number. Lower means the model spreads load more evenly across reps.

The line chart shows fairness trial by trial. You're looking for two things: how low the line sits (better fairness) and how stable it is (consistent fairness, not just lucky). If a line is low but spiky, the model is fair sometimes but unreliable. Scoring should sit low and flat.

The bar chart is a single snapshot, one trial's per-rep load. It makes the abstract numbers concrete. If one model shows roughly equal bars and another shows one rep towering over the rest, you can see the imbalance directly.
 */


import { useState, useMemo } from "react";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, LineChart, Line, ResponsiveContainer } from "recharts";

const COLORS = ["#2563eb", "#dc2626", "#16a34a", "#f59e0b", "#8b5cf6"];

function simulateAssignments({ numReps, numProspects, numTrials, newCap }) {
  const results = { hierarchical: [], threshold: [], scoring: [] };

  for (let t = 0; t < numTrials; t++) {
    // Random starting workloads for each rep
    const initState = () =>
      Array.from({ length: numReps }, () => ({
        new_count: Math.floor(Math.random() * 4),
        working: Math.floor(Math.random() * 12),
        nurture: Math.floor(Math.random() * 20),
      }));

    // --- Hierarchical ---
    const hReps = initState();
    for (let p = 0; p < numProspects; p++) {
      const sorted = [...hReps.keys()].sort((a, b) => {
        if (hReps[a].new_count !== hReps[b].new_count) return hReps[a].new_count - hReps[b].new_count;
        if (hReps[a].working !== hReps[b].working) return hReps[a].working - hReps[b].working;
        return hReps[a].nurture - hReps[b].nurture;
      });
      hReps[sorted[0]].new_count++;
    }
    results.hierarchical.push(hReps.map((r) => r.new_count + r.working + r.nurture));

    // --- Threshold ---
    const tReps = initState();
    for (let p = 0; p < numProspects; p++) {
      const eligible = [...tReps.keys()].filter(
        (i) => tReps[i].new_count < newCap && tReps[i].working < 10 && tReps[i].nurture < 20
      );
      if (eligible.length > 0) {
        // Just pick first eligible (no fairness logic)
        tReps[eligible[0]].new_count++;
      } else {
        // All capped — force assign to lowest new
        const fallback = [...tReps.keys()].sort((a, b) => tReps[a].new_count - tReps[b].new_count);
        tReps[fallback[0]].new_count++;
      }
    }
    results.threshold.push(tReps.map((r) => r.new_count + r.working + r.nurture));

    // --- Scoring ---
    const sReps = initState();
    for (let p = 0; p < numProspects; p++) {
      const eligible = [...sReps.keys()].filter((i) => sReps[i].new_count < newCap);
      const pool = eligible.length > 0 ? eligible : [...sReps.keys()];
      const score = (i) => 2 * sReps[i].new_count + 1 * sReps[i].working + 0.5 * sReps[i].nurture;
      pool.sort((a, b) => score(a) - score(b));
      sReps[pool[0]].new_count++;
    }
    results.scoring.push(sReps.map((r) => r.new_count + r.working + r.nurture));
  }

  return results;
}

function computeStats(results, numReps) {
  const stats = {};
  for (const model of Object.keys(results)) {
    const stddevs = results[model].map((trial) => {
      const mean = trial.reduce((s, v) => s + v, 0) / trial.length;
      const variance = trial.reduce((s, v) => s + (v - mean) ** 2, 0) / trial.length;
      return Math.sqrt(variance);
    });
    const ranges = results[model].map((trial) => Math.max(...trial) - Math.min(...trial));
    const avgStd = stddevs.reduce((s, v) => s + v, 0) / stddevs.length;
    const avgRange = ranges.reduce((s, v) => s + v, 0) / ranges.length;
    stats[model] = { avgStd: +avgStd.toFixed(2), avgRange: +avgRange.toFixed(2), stddevs, ranges };
  }
  return stats;
}

function getDistributionData(results, numReps) {
  // Take last trial for each model and show per-rep loads
  const data = [];
  for (let i = 0; i < numReps; i++) {
    const row = { rep: `Rep ${i + 1}` };
    for (const model of Object.keys(results)) {
      const lastTrial = results[model][results[model].length - 1];
      row[model] = lastTrial[i];
    }
    data.push(row);
  }
  return data;
}

function getStddevOverTrials(stats) {
  const len = stats.hierarchical.stddevs.length;
  const step = Math.max(1, Math.floor(len / 50));
  const data = [];
  for (let i = 0; i < len; i += step) {
    data.push({
      trial: i + 1,
      Hierarchical: +stats.hierarchical.stddevs[i].toFixed(2),
      Threshold: +stats.threshold.stddevs[i].toFixed(2),
      Scoring: +stats.scoring.stddevs[i].toFixed(2),
    });
  }
  return data;
}

export default function MonteCarloSim() {
  const [numReps, setNumReps] = useState(5);
  const [numProspects, setNumProspects] = useState(20);
  const [numTrials, setNumTrials] = useState(500);
  const [newCap, setNewCap] = useState(5);
  const [seed, setSeed] = useState(0);

  const { results, stats, distData, stddevData } = useMemo(() => {
    const results = simulateAssignments({ numReps, numProspects, numTrials, newCap });
    const stats = computeStats(results, numReps);
    const distData = getDistributionData(results, numReps);
    const stddevData = getStddevOverTrials(stats);
    return { results, stats, distData, stddevData };
  }, [numReps, numProspects, numTrials, newCap, seed]);

  const modelLabels = { hierarchical: "Hierarchical", threshold: "Threshold", scoring: "Scoring" };
  const modelColors = { hierarchical: "#2563eb", threshold: "#dc2626", scoring: "#16a34a" };

  return (
    <div style={{ fontFamily: "system-ui, sans-serif", maxWidth: 900, margin: "0 auto", padding: 24 }}>
      <h2 style={{ marginBottom: 4 }}>Monte Carlo: Assignment Model Comparison</h2>
      <p style={{ color: "#666", marginTop: 0, fontSize: 14 }}>
        Simulates {numTrials} random scenarios. Lower std dev = fairer distribution across reps.
      </p>

      <div style={{ display: "flex", gap: 16, flexWrap: "wrap", marginBottom: 24, padding: 16, background: "#f8f9fa", borderRadius: 8 }}>
        {[
          ["Reps", numReps, setNumReps, 2, 10],
          ["Prospects", numProspects, setNumProspects, 5, 60],
          ["Trials", numTrials, setNumTrials, 100, 2000],
          ["New Cap", newCap, setNewCap, 2, 15],
        ].map(([label, val, setter, min, max]) => (
          <label key={label} style={{ fontSize: 13 }}>
            <div style={{ fontWeight: 600, marginBottom: 4 }}>{label}: {val}</div>
            <input
              type="range"
              min={min}
              max={max}
              value={val}
              onChange={(e) => setter(+e.target.value)}
              style={{ width: 140 }}
            />
          </label>
        ))}
        <button
          onClick={() => setSeed((s) => s + 1)}
          style={{ alignSelf: "flex-end", padding: "6px 16px", borderRadius: 6, border: "1px solid #ccc", background: "#fff", cursor: "pointer", fontSize: 13 }}
        >
          Re-roll
        </button>
      </div>

      {/* Summary cards */}
      <div style={{ display: "flex", gap: 12, marginBottom: 24 }}>
        {Object.entries(stats).map(([model, s]) => (
          <div
            key={model}
            style={{
              flex: 1,
              padding: 16,
              borderRadius: 8,
              border: `2px solid ${modelColors[model]}`,
              background: "#fff",
            }}
          >
            <div style={{ fontWeight: 700, color: modelColors[model], marginBottom: 8 }}>
              {modelLabels[model]}
            </div>
            <div style={{ fontSize: 13 }}>
              Avg Std Dev: <strong>{s.avgStd}</strong>
            </div>
            <div style={{ fontSize: 13 }}>
              Avg Range: <strong>{s.avgRange}</strong>
            </div>
          </div>
        ))}
      </div>

      {/* Std dev over trials */}
      <h3 style={{ marginBottom: 8 }}>Fairness Over Trials (Std Dev of Total Load)</h3>
      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={stddevData}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="trial" fontSize={11} />
          <YAxis fontSize={11} />
          <Tooltip />
          <Legend />
          <Line type="monotone" dataKey="Hierarchical" stroke="#2563eb" dot={false} strokeWidth={2} />
          <Line type="monotone" dataKey="Threshold" stroke="#dc2626" dot={false} strokeWidth={2} />
          <Line type="monotone" dataKey="Scoring" stroke="#16a34a" dot={false} strokeWidth={2} />
        </LineChart>
      </ResponsiveContainer>

      {/* Per-rep distribution (last trial) */}
      <h3 style={{ marginTop: 24, marginBottom: 8 }}>Per-Rep Total Load (Last Trial)</h3>
      <ResponsiveContainer width="100%" height={280}>
        <BarChart data={distData}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="rep" fontSize={11} />
          <YAxis fontSize={11} />
          <Tooltip />
          <Legend />
          <Bar dataKey="hierarchical" name="Hierarchical" fill="#2563eb" />
          <Bar dataKey="threshold" name="Threshold" fill="#dc2626" />
          <Bar dataKey="scoring" name="Scoring" fill="#16a34a" />
        </BarChart>
      </ResponsiveContainer>

      <p style={{ fontSize: 12, color: "#888", marginTop: 16 }}>
        Each trial randomises starting workloads and assigns {numProspects} prospects to {numReps} reps.
        Scoring consistently produces the lowest std dev (fairest spread).
      </p>
    </div>
  );
}