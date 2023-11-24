import pytest
from my_preprocessing.raw_data_loader import RawDataLoader, RAW_PATH


@pytest.mark.parametrize(
    "use_icu, target, target_time, disease_label, icd_code_filter, expected_admission_records_count, expected_patients_count, expected_positive_cases_count",
    [
        ("ICU", "Mortality", 0, "", "No Disease Filter", 140, 100, 10),
        ("ICU", "Length of Stay", 3, "", "No Disease Filter", 140, 100, 55),
        ("ICU", "Length of Stay", 7, "", "No Disease Filter", 140, 100, 20),
        ("ICU", "Readmission", 30, "", "No Disease Filter", 128, 93, 18),
        ("ICU", "Readmission", 90, "", "No Disease Filter", 128, 93, 22),
        ("ICU", "Readmission", 30, "I50", "No Disease Filter", 27, 20, 2),
        # heart failure
        ("ICU", "Readmission", 30, "I25", "No Disease Filter", 32, 29, 2),  # CAD
        ("ICU", "Readmission", 30, "N18", "No Disease Filter", 25, 18, 2),  # CKD
        ("ICU", "Readmission", 30, "J44", "No Disease Filter", 17, 12, 3),  # COPD
        ("Non-ICU", "Mortality", 0, "", "No Disease Filter", 275, 100, 15),
        ("Non-ICU", "Length of Stay", 3, "", "No Disease Filter", 275, 100, 163),
        ("Non-ICU", "Length of Stay", 7, "", "No Disease Filter", 275, 100, 76),
        ("Non-ICU", "Readmission", 30, "", "No Disease Filter", 260, 95, 52),
        ("Non-ICU", "Readmission", 90, "", "No Disease Filter", 260, 95, 86),
        ("Non-ICU", "Readmission", 30, "I50", "No Disease Filter", 55, 23, 13),
        # heart failure
        ("Non-ICU", "Readmission", 30, "I25", "No Disease Filter", 68, 32, 13),  # CAD
        ("Non-ICU", "Readmission", 30, "N18", "No Disease Filter", 63, 22, 10),  # CKD
        ("Non-ICU", "Readmission", 30, "J44", "No Disease Filter", 26, 12, 7),  # COPD
        ("ICU", "Mortality", 0, "", "I50", 32, 22, 5),
    ],
)
def test_extract_icu_mortality(
    use_icu,
    target,
    target_time,
    disease_label,
    icd_code_filter,
    expected_admission_records_count,
    expected_patients_count,
    expected_positive_cases_count,
):
    raw_data_loader = RawDataLoader(
        use_icu=use_icu,
        label=target,
        time=target_time,
        icd_code=icd_code_filter,
        raw_dir=RAW_PATH,
        preproc_dir="",
        disease_label=disease_label,
        cohort_output="",
        summary_output="",
    )
    visits_patients = raw_data_loader.extract()
    assert len(visits_patients) == expected_admission_records_count
    assert visits_patients["subject_id"].nunique() == expected_patients_count
    assert visits_patients["label"].sum() == expected_positive_cases_count
