# Demo video script (target 3:00, hard limit 4:00)

Setup before recording: Zetaris running in Docker, Nightshift open and running, `bash .step.sh`-style server started with `python3 -m agent.server` (SAMPLE_MODE=false), browser at http://localhost:8000. Click "Forget what the agent learned". Hide Terminal and Nightshift's key screens. No .env on screen.

1. 0:00 to 0:20, the problem. Say: "A deploy fails. CI is green. Five commits landed. Which one broke production? This is Build-Failure Detective, my solo entry for Track 2."
2. 0:20 to 0:50, Zetaris. Show the Zetaris console or the report's data line: "The agent reads commits, deploys, logs and CI from Zetaris with SQL. Here is the query it ran." (Open the first trace lines, or the "Loaded data from Zetaris" step in the app.)
3. 0:50 to 1:40, a real request through Nightshift. Pick "Live data from Zetaris", tick the Nemotron box, press Investigate. While it runs say: "This goes through Meterless Nightshift to NVIDIA Nemotron." Show Nightshift's window with the request, then the result: Confirmed, evidence ids, and the line "Written by nvidia/nemotron-3-ultra". Point at the evidence chips: "Every claim cites its source and was checked."
4. 1:40 to 2:20, H-MEM. Click the "Same failure, different names" incident and Investigate. Say: "Memory recalled a lesson from the first incident, so this took one round instead of four. The evaluator still verified every check." Point at the "memory-guided" tag and the memory steps in the timeline.
5. 2:20 to 2:45, it can say no. Run "No code change explains it". Say: "When nothing explains the failure, it says inconclusive and blames no one."
6. 2:45 to 3:00, close. Say: "Zetaris for the data, H-MEM for learning, Nightshift and Nemotron for the explanation. Code and README are on GitHub."
