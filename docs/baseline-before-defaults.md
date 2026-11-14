# Baseline before dashboard default removal

Generated before changing default handling. This file contains aggregated counts only;
it contains no patient identifiers or row-level values.

## Cohort

- Total evaluated records: 58.

## KPI baseline

| Area | KPI | Value |
| --- | --- | ---: |
| Summary | Hypertension | 31.0% |
| Summary | Dyslipidemia | 37.9% |
| Summary | Overweight or obesity | 82.8% |
| Summary | High risk (2+ factors) | 50.0% |
| Individual | Mean age | 57.1 years |
| Individual | Men / women | 50.0% / 50.0% |
| Individual | Postgraduate / married | 82.8% / 60.3% |
| Physical | Mean BMI / waist risk | 29.0 / 39.7% |
| Physical | Mean SBP / DBP / SpO2 | 126 / 75 / 98 |
| Modifiable | HTN / DM / dyslipidemia / smoking / activity | 31.0% / 0.0% / 37.9% / 12.1% / 32.8% |
| Emerging | Poor sleep / stress / work environment / type A / toxins | 22.4% / 43.1% / 1.7% / 13.8% / 0.0% |
| Family | HTN / DM / dyslipidemia / major CV event | 53.4% / 32.8% / 20.7% / 0.0% |
| Non-cardiac | Respiratory / mental / rheumatologic / allergy | 6.9% / 10.3% / 1.7% / 3.4% |
| COVID | Infection / hospitalization / sequelae / persistent fatigue | 84.5% / 0.0% / 3.4% / 3.4% |
| ECG | Sinus / arrhythmia | 100.0% / 0.0% |
| ECG | Mean PR / QRS / QTc | 166 / 102 / 410 ms |

## Chart baselines

| Chart data | Aggregated values |
| --- | --- |
| Year | 2026: 58 |
| Personnel category | PAS: 26; PDI: 26; Services: 4; Students: 2 |
| Age group | <40: 24; 40-49: 22; 50-59: 4; 60+: 8 |
| Civil status | Married: 35; Divorced: 7; Single: 16 |
| Education | Postgraduate: 48; Secondary: 3; Higher: 7 |
| Housing | Own: 38; Family: 14; Other: 6 |
| BMI | Normal: 10; Overweight: 26; Obesity I: 18; II: 2; morbid: 2 |
| BP category | Normal: 33; elevated: 13; HTN I: 11; HTN II: 1 |
| Tobacco | Active: 7; non-smoker: 51 |
| Alcohol | None: 43; occasional: 7; weekly: 8 |
| Sleep quality | Good: 43; poor: 13; normal: 2 |
| Sleep quantity | Adequate: 43; insufficient: 14; normal: 1 |
| Stress | None: 33; work: 15; family: 7; both: 3 |
| Risk level | Low: 10; moderate: 19; high: 22; very high: 7 |
| ECG PR | Normal: 54; AV block I: 3; not measured: 1 |
| ECG QRS | Normal: 46; incomplete: 7; complete block: 4; not measured: 1 |
| ECG QTc | Normal male threshold: 27; normal female threshold: 28; prolonged: 2; not measured: 1 |
| ECG branch block | None: 57; incomplete right branch: 1 |

## Step-1 source-value completeness baseline

Empty counts use the current raw source relation or recorded answer, before the
dashboard imposes its fallback value.

| Variable group | Empty | Total | Empty % |
| --- | ---: | ---: | ---: |
| Sex relation | 0 | 58 | 0.0% |
| Education relation | 4 | 58 | 6.9% |
| Housing relation | 0 | 58 | 0.0% |
| Weight | 0 | 58 | 0.0% |
| Height | 0 | 58 | 0.0% |
| Heart rate | 0 | 58 | 0.0% |
| Oxygen saturation | 0 | 58 | 0.0% |
| ECG relation | 0 | 58 | 0.0% |
| Tobacco answer | 0 | 58 | 0.0% |
| Alcohol answer | 0 | 58 | 0.0% |
| Sleep quality answer | 2 | 58 | 3.4% |
| Sleep quantity answer | 1 | 58 | 1.7% |
| Stress answer group | 8 | 58 | 13.8% |
| Activity answer group | 9 | 58 | 15.5% |
| Family-history answer group | 18 | 58 | 31.0% |
| Respiratory history answer group | 0 | 58 | 0.0% |
| Mental-health answer group | 0 | 58 | 0.0% |
| Rheumatology answer group | 14 | 58 | 24.1% |
| Cancer answer group | 6 | 58 | 10.3% |
| Medication-allergy answer group | 4 | 58 | 6.9% |
| Renal-insufficiency answer group | 3 | 58 | 5.2% |

## Known baseline limitations

- Existing model booleans can persist a default `False`; for those columns,
  historical “No” and omitted input cannot be reconstructed safely.
- Values in the visible dashboard may differ from raw completeness because
  `services.py` currently supplies clinical defaults. This is the subject of
  the subsequent change.
