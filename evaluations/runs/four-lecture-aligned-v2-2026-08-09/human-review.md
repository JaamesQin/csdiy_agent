# Human adjudication

The reviewer inspected every Critical finding and every within-lecture score spread greater than 10 points after blind scoring and before applying the mode labels.

- Lecture 08 fast attempt 1 (74, Critical): confirmed. The artifact defines `A=softmax(s)` but never defines `s=QK^T/sqrt(m)` or otherwise supplies the required scaling. Attempts 2 and 3 independently scored 97 and 98 with no Critical, so the majority outcome is zero Critical and the three-attempt mean is 89.667.
- Lecture 02 spread (91 fast, 96 standard, 84 strict): confirmed as a representation difference, not scorer identity bias. Strict includes the mathematical claims in prose but has an empty structured formula inventory; standard has the fullest reviewable representation.
- Lecture 03 spread (74 fast, 82 standard, 91 strict): confirmed. Fast has over-escaped LaTeX and no `formula_unresolved`; strict preserves the constants and formulas well but also omits the required unresolved marker. The relative scores follow visible artifact differences.
- Lecture 08 initial spread (74 fast, 98 standard, 97 strict): the first-attempt gap was real. The protocol-controlled reruns remove it (fast majority score mean 89.667), without exposing the defect to the generator.

No score was changed during adjudication.
