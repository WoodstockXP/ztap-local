import csv
import re
import sys
from collections import defaultdict

TIER1_LINE = re.compile(r"^\[(PASS|FAIL)\]\s+(\S+):")
TIER2_RUNNING = re.compile(r"^Running\s+(\S+):")
TIER2_OUTCOME = re.compile(r"^\s*->\s*(.+?):\s")


def parse_tier1(text):
    outcomes = {}
    for line in text.splitlines():
        m = TIER1_LINE.match(line)
        if m:
            status, case_id = m.groups()
            outcomes[case_id] = status
    return outcomes


def parse_tier2(text):
    outcomes = {}
    current = None
    for line in text.splitlines():
        m = TIER2_RUNNING.match(line)
        if m:
            current = m.group(1)
            continue
        m = TIER2_OUTCOME.match(line)
        if m and current:
            outcomes[current] = m.group(1)
            current = None
    return outcomes


def main():
    if len(sys.argv) != 2:
        print("usage: python eval/analyze_matrix.py <results_dir>")
        sys.exit(1)
    results_dir = sys.argv[1]
    manifest_path = f"{results_dir}/manifest.csv"
    rows = list(csv.DictReader(open(manifest_path)))

    durations = defaultdict(list)
    crashed = defaultdict(list)
    case_outcomes = defaultdict(lambda: defaultdict(list))

    for row in rows:
        key = (row["topology"], row["tenant"], row["tier"])
        durations[key].append(float(row["duration_seconds"]))
        if row["exit_code"] != "0":
            crashed[key].append(row["run"])
        try:
            text = open(row["log_file"]).read()
        except OSError as exc:
            print(f"warning: could not read {row['log_file']}: {exc}", file=sys.stderr)
            continue
        parser = parse_tier1 if row["tier"] == "tier1" else parse_tier2
        for case_id, outcome in parser(text).items():
            case_outcomes[key][case_id].append(outcome)

    print("=== Duration summary ===\n")
    for key in sorted(durations):
        vals = durations[key]
        n = len(vals)
        mean = sum(vals) / n
        print(f"{key[0]}/{key[1]}/{key[2]}: n={n} mean={mean:.2f}s min={min(vals):.2f}s max={max(vals):.2f}s")

    print("\n=== Crashed runs (nonzero exit code) ===\n")
    any_crash = False
    for key, runs in crashed.items():
        any_crash = True
        print(f"{key[0]}/{key[1]}/{key[2]}: runs {', '.join(runs)}")
    if not any_crash:
        print("none")

    print("\n=== Inconsistent test case outcomes across repeated runs ===\n")
    any_inconsistent = False
    for key in sorted(case_outcomes):
        for case_id, outcomes in sorted(case_outcomes[key].items()):
            distinct = set(outcomes)
            if len(distinct) > 1:
                any_inconsistent = True
                counts = {o: outcomes.count(o) for o in distinct}
                print(f"{key[0]}/{key[1]}/{key[2]} {case_id}: {counts}")
    if not any_inconsistent:
        print("none, every test case produced the same outcome on every run")


if __name__ == "__main__":
    main()
