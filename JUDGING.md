# Judging and ranking

FairPanel computes results separately within each event track. A review is eligible for ranking only after it is submitted and its assignment is marked complete. Missing reviews do not count as zero. A project with no eligible review has no score or rank.

## Assignment

Organizers can create manual pairs or request a balanced batch. Both paths require the judge to be a member of that event, have an explicit track scope covering the project, and not belong to the project's team. The balanced path processes eligible projects in stable ID order and chooses the available judge with the smallest assignment count, using judge ID to break ties. It preserves existing assignments and reports projects with insufficient eligible judges. Reported conflicts suspend scoring for that pair. This greedy method is deterministic, but does not optimize global overlap or guarantee equal workloads.

## Raw scores

For criterion `c`, with configured lower/upper bounds `L_c`, `U_c`, weight `w_c`, and review score `x_c`, the contribution is:

```text
normalized_c = (x_c - L_c) / (U_c - L_c)
review_score = 100 * sum(w_c * normalized_c) / sum(w_c)
project_raw_score = mean(complete submitted review_scores for the project)
```

Rubric writes reject duplicate keys, nonfinite values, invalid ranges, negative weights, and zero total weight. Review submission requires every criterion to be present and within its range. Rubrics lock once submitted scoring starts. Internal calculations retain full precision; display and exports round to two decimals. Raw ranks use descending score within each track. Scores equal within `1e-5` share a competition rank: `1, 1, 3`, with stable project IDs used only for display order.

## Optional severity adjustment (`overlap_bias_v1`)

Within one track and rubric version, the algorithm compares each judge with peers on projects they both reviewed. For each overlap, it subtracts the mean of the peers' review scores from that judge's score. The mean of these differences estimates whether the judge tends to score above or below their peers. With `n` overlap projects, the estimate is multiplied by `n / (n + 5)` before correction. The constant `5` is a conservative heuristic, not a fitted statistical parameter.

A judge is calibrated only after at least three overlapping project reviews, provided their scores are not constant and the reviewer overlap graph is connected. Otherwise their correction is zero and their score is flagged as uncalibrated. A reviewer who gives the same score to every project is flagged for human review, never automatically excluded. An adjusted project score averages its reviewers' raw scores minus their individual severity corrections. That adjusted index can lie outside 0–100; it is not clipped because clipping could change ranks.

If no judge in a track can be calibrated, or the overlap graph is disconnected, adjusted scores and ranks for that track are unavailable. Publication with the adjusted method is rejected unless adjusted ranks exist for every included project. The organizer can still inspect and publish raw ranks, with coverage warnings.

For example, suppose two judges review three common projects. Judge A gives `20, 40, 60`; judge B gives `40, 60, 80`. A's mean peer difference is `-20`, B's is `+20`, and the shrink factor is `3/8`. The corrections are `-7.5` and `+7.5`. Their adjusted reviews are `27.5, 47.5, 67.5` and `32.5, 52.5, 72.5`; the project means remain `30, 50, 70`. This example shows the calculation and does not claim that a rank change is evidence of fairness.

The adjustment assumes comparable project populations, sufficiently overlapping reviewers, and a roughly stable additive judge tendency. It does not establish project quality, remove selection bias, prevent collusion, or calibrate disconnected groups. Results should always show raw and adjusted values, coverage, and warnings to the organizer.

## Publication

The organizer previews results and receives a fingerprint of project, review, assignment, and rubric inputs. Publication requires that exact fingerprint and a selected raw or adjusted method. The application writes a result revision containing scores, ranks, titles, and track labels. Once a snapshot exists, project content, eligibility, assignments, and reviews are locked through ordinary endpoints. Public results read the latest snapshot. The audit trail records publication, but it is an application log rather than a cryptographic proof.
