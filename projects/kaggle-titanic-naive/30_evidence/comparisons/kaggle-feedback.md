# Kaggle Feedback Comparison

Kaggle competition: titanic

Metric: public leaderboard accuracy

Evaluation boundary: Kaggle; LASI did not access hidden labels.

| Experiment | Component configuration | Local holdout accuracy | Kaggle submission | Public score | Interpretation |
| --- | --- | ---: | ---: | ---: | --- |
| titanic-naive-logistic-v1 | CSV dataset -> stratified holdout -> naive logistic regression -> evaluation | 0.82682 | 55470945 | 0.76794 | Reproducible evidence floor. |
| titanic-title-family-logistic-v1 | CSV dataset -> title/family features -> stratified holdout -> logistic regression -> evaluation | 0.83799 | 55470993 | 0.77511 | Improved over the naive baseline, but not the existing best. |
| Prior LASI best | categorical combination of Sex, Pclass, Embarked, and Title | not reconstructed in this project | 55210331 | 0.78229 | Remains the best observed public score. |

## Decision

Stop this branch as research_only. The title/family component is a useful
reusable capability because it improved the naive baseline by 0.00717 on the
public leaderboard, but the available evidence does not justify another
unplanned variant. Any continuation must start with a new hypothesis that
explains how it could surpass 0.78229 and must be approved through LASI's
normal plan and decision path.
