from pathlib import Path
import pandas as pd
import my_preprocessing.disease_cohort as disease_cohort
import datetime
import logging
import numpy as np
from tqdm import tqdm

logger = logging.getLogger()


RAW_PATH = Path("raw_data") / "mimiciv_2_0"

# TODO
# use_icu: bool


class RawDataLoader:
    def __init__(
        self,
        use_icu: str,
        label: str,
        time: int,
        icd_code: str,
        raw_dir: Path,
        preproc_dir: Path,
        disease_label: str,
        cohort_output: Path,
        summary_output: Path,
    ):
        self.use_icu = use_icu
        self.label = label
        self.time = time
        self.icd_code = icd_code
        self.raw_dir = raw_dir
        self.preproc_dir = preproc_dir
        self.disease_label = disease_label
        self.cohort_output = cohort_output
        self.summary_output = summary_output

    def output_suffix(self) -> str:
        return (
            self.use_icu.lower()
            + "_"
            + self.label.lower().replace(" ", "_")
            + "_"
            + str(self.time)
            + "_"
            + self.disease_label
        )

    def fill_outputs(self) -> None:
        if not self.cohort_output:
            self.cohort_output = "cohort_" + self.output_suffix()
        if not self.summary_output:
            self.summary_output = "summary_" + self.output_suffix()

    # TODO: CLARIFY LOG
    def log_extracting_for(self) -> str:
        if self.icd_code == "No Disease Filter":
            if len(self.disease_label):
                return f"EXTRACTING FOR: | {self.use_icu.upper()} | {self.label.upper()} DUE TO {self.disease_label.upper()} | {str(self.time)} | "
            return f"EXTRACTING FOR: | {self.use_icu.upper()} | {self.label.upper()} | {str(self.time)} |"
        else:
            if len(self.disease_label):
                return f"EXTRACTING FOR: | {self.use_icu.upper()} | {self.label.upper()} DUE TO {self.disease_label.upper()} | ADMITTED DUE TO {self.icd_code.upper()} | {str(self.time)} |"
        return f"EXTRACTING FOR: | {self.use_icu.upper()} | {self.label.upper()} | ADMITTED DUE TO {self.icd_code.upper()} | {str(self.time)} |"

    def load_hosp_patients(self):
        patients = pd.read_csv(
            self.raw_dir / "hosp" / "patients.csv.gz",
            compression="gzip",
            header=0,
            parse_dates=["dod"],
        )
        return patients

    def load_hosp_admissions(self):
        hosp_admissions = pd.read_csv(
            self.raw_dir / "hosp" / "admissions.csv.gz",
            compression="gzip",
            header=0,
            index_col=None,
            parse_dates=["admittime", "dischtime"],
        )
        return hosp_admissions

    def load_icu_icustays(self):
        visits = pd.read_csv(
            self.raw_dir / "icu" / "icustays.csv.gz",
            compression="gzip",
            header=0,
            parse_dates=["intime", "outtime"],
        )
        return visits

    def load_no_icu_visits(self) -> pd.DataFrame:
        hosp_admissions = self.load_hosp_admissions()
        dischtimes = hosp_admissions["dischtime"]
        admittimes = hosp_admissions["admittime"]
        hosp_admissions["los"] = dischtimes - admittimes
        hosp_admissions["admittime"] = pd.to_datetime(admittimes)
        hosp_admissions["dischtime"] = pd.to_datetime(dischtimes)

        # simplify....
        hosp_admissions["los"] = pd.to_timedelta(dischtimes - admittimes, unit="h")
        hosp_admissions["los"] = hosp_admissions["los"].astype(str)
        hosp_admissions["los"] = pd.to_numeric(
            hosp_admissions["los"].str.split(expand=True)[0]
        )
        if self.label == "Readmission":
            # remove hospitalizations with a death; impossible for readmission for such visits
            hosp_admissions = hosp_admissions.loc[
                hosp_admissions.hospital_expire_flag == 0
            ]
        if len(self.disease_label):
            hids = disease_cohort.extract_diag_cohort(
                hosp_admissions["hadm_id"], self.disease_label, self.raw_dir
            )
            hosp_admissions = hosp_admissions[
                hosp_admissions["hadm_id"].isin(hids["hadm_id"])
            ]
            print("[ READMISSION DUE TO " + self.disease_label + " ]")
        return hosp_admissions

    def load_icu_visits(self) -> pd.DataFrame:
        icu_icustays = self.load_icu_icustays()
        if self.label != "Readmission":
            return icu_icustays
        # icustays doesn't have a way to identify if patient died during visit; must
        # use core/patients to remove such stay_ids for readmission labels
        hosp_patient = self.load_hosp_patients()[["subject_id", "dod"]]
        visits = icu_icustays.merge(
            hosp_patient, how="inner", left_on="subject_id", right_on="subject_id"
        )
        visits = visits.loc[(visits.dod.isna()) | (visits.dod >= visits["outtime"])]
        if len(self.disease_label):
            hids = disease_cohort.extract_diag_cohort(
                visits["hadm_id"], self.disease_label, self.raw_dir
            )
            visits = visits[visits["hadm_id"].isin(hids["hadm_id"])]
            print("[ READMISSION DUE TO " + self.disease_label + " ]")
        return visits

    def load_visits(self) -> pd.DataFrame:
        if self.use_icu == "ICU":
            return self.load_icu_visits()
        return self.load_no_icu_visits()

    def load_patients(self) -> pd.DataFrame:
        hosp_patients = self.load_hosp_patients()[
            [
                "subject_id",
                "anchor_year",
                "anchor_age",
                "anchor_year_group",
                "dod",
                "gender",
            ]
        ]
        hosp_patients["yob"] = (
            hosp_patients["anchor_year"] - hosp_patients["anchor_age"]
        )  # get yob to ensure a given visit is from an adult
        hosp_patients["min_valid_year"] = hosp_patients["anchor_year"] + (
            2019 - hosp_patients["anchor_year_group"].str.slice(start=-4).astype(int)
        )

        # Define anchor_year corresponding to the anchor_year_group 2017-2019. This is later used to prevent consideration
        # of visits with prediction windows outside the dataset's time range (2008-2019)
        return hosp_patients

    def partition_by_los(
        self,
        df: pd.DataFrame,
        los: int,
        group_col: str,
        visit_col: str,
        admit_col: str,
        disch_col: str,
        valid_col: str,
    ):
        invalid = df.loc[
            (df[admit_col].isna()) | (df[disch_col].isna()) | (df["los"].isna())
        ]
        cohort = df.loc[
            (~df[admit_col].isna()) & (~df[disch_col].isna()) & (~df["los"].isna())
        ]

        # cohort=cohort.fillna(0)
        pos_cohort = cohort[cohort["los"] > los]
        neg_cohort = cohort[cohort["los"] <= los]
        neg_cohort = neg_cohort.fillna(0)
        pos_cohort = pos_cohort.fillna(0)

        pos_cohort["label"] = 1
        neg_cohort["label"] = 0

        cohort = pd.concat([pos_cohort, neg_cohort], axis=0)
        cohort = cohort.sort_values(by=[group_col, admit_col])
        # print("cohort",cohort.shape)
        print("[ LOS LABELS FINISHED ]")
        return cohort, invalid

    def partition_by_readmit(
        self,
        df: pd.DataFrame,
        gap: datetime.timedelta,
        group_col: str,
        visit_col: str,
        admit_col: str,
        disch_col: str,
        valid_col: str,
    ):
        """Applies labels to individual visits according to whether or not a readmission has occurred within the specified `gap` days.
        For a given visit, another visit must occur within the gap window for a positive readmission label.
        The gap window starts from the disch_col time and the admit_col of subsequent visits are considered.
        """

        case = pd.DataFrame()  # hadm_ids with readmission within the gap period
        ctrl = pd.DataFrame()  # hadm_ids without readmission within the gap period
        invalid = pd.DataFrame()  # hadm_ids that are not considered in the cohort

        # Iterate through groupbys based on group_col (subject_id). Data is sorted by subject_id and admit_col (admittime)
        # to ensure that the most current hadm_id is last in a group.
        # grouped= df[[group_col, visit_col, admit_col, disch_col, valid_col]].sort_values(by=[group_col, admit_col]).groupby(group_col)
        grouped = df.sort_values(by=[group_col, admit_col]).groupby(group_col)
        for subject, group in tqdm(grouped):
            max_year = group.max()[disch_col].year

            if group.shape[0] <= 1:
                # ctrl, invalid = validate_row(group.iloc[0], ctrl, invalid, max_year, disch_col, valid_col, gap)   # A group with 1 row has no readmission; goes to ctrl
                ctrl = pd.concat(
                    [ctrl, pd.DataFrame([group.iloc[0]])], ignore_index=True
                )
            else:
                for idx in range(group.shape[0] - 1):
                    visit_time = group.iloc[idx][
                        disch_col
                    ]  # For each index (a unique hadm_id), get its timestamp
                    if (
                        group.loc[
                            (group[admit_col] > visit_time)
                            & (  # Readmissions must come AFTER the current timestamp
                                group[admit_col] - visit_time <= gap
                            )  # Distance between a timestamp and readmission must be within gap
                        ].shape[0]
                        >= 1
                    ):  # If ANY rows meet above requirements, a readmission has occurred after that visit
                        case = pd.concat(
                            [case, pd.DataFrame([group.iloc[idx]])], ignore_index=True
                        )
                    else:
                        # If no readmission is found, only add to ctrl if prediction window is guaranteed to be within the
                        # time range of the dataset (2008-2019). Visits with prediction windows existing in potentially out-of-range
                        # dates (like 2018-2020) are excluded UNLESS the prediction window takes place the same year as the visit,
                        # in which case it is guaranteed to be within 2008-2019

                        ctrl = pd.concat(
                            [ctrl, pd.DataFrame([group.iloc[idx]])], ignore_index=True
                        )

                # ctrl, invalid = validate_row(group.iloc[-1], ctrl, invalid, max_year, disch_col, valid_col, gap)  # The last hadm_id datewise is guaranteed to have no readmission logically
                ctrl = pd.concat(
                    [ctrl, pd.DataFrame([group.iloc[-1]])], ignore_index=True
                )
                # print(f"[ {gap.days} DAYS ] {case.shape[0] + ctrl.shape[0]}/{df.shape[0]} {visit_col}s processed")

        print("[ READMISSION LABELS FINISHED ]")
        return case, ctrl, invalid

    def partition_by_mort(
        self,
        df: pd.DataFrame,
        group_col: str,
        visit_col: str,
        admit_col: str,
        disch_col: str,
        death_col: str,
    ):
        """Applies labels to individual visits according to whether or not a death has occurred within
        the times of the specified admit_col and disch_col"""

        invalid = df.loc[(df[admit_col].isna()) | (df[disch_col].isna())]

        cohort = df.loc[(~df[admit_col].isna()) & (~df[disch_col].isna())]

        cohort["label"] = 0
        # cohort=cohort.fillna(0)
        pos_cohort = cohort[~cohort[death_col].isna()]
        neg_cohort = cohort[cohort[death_col].isna()]
        neg_cohort = neg_cohort.fillna(0)
        pos_cohort = pos_cohort.fillna(0)
        pos_cohort[death_col] = pd.to_datetime(pos_cohort[death_col])

        pos_cohort["label"] = np.where(
            (pos_cohort[death_col] >= pos_cohort[admit_col])
            & (pos_cohort[death_col] <= pos_cohort[disch_col]),
            1,
            0,
        )

        pos_cohort["label"] = pos_cohort["label"].astype("Int32")
        cohort = pd.concat([pos_cohort, neg_cohort], axis=0)
        cohort = cohort.sort_values(by=[group_col, admit_col])
        # print("cohort",cohort.shape)
        print("[ MORTALITY LABELS FINISHED ]")
        return cohort, invalid

    def get_case_ctrls(
        self,
        df: pd.DataFrame,
        gap: int,
        group_col: str,
        visit_col: str,
        admit_col: str,
        disch_col: str,
        valid_col: str,
        death_col: str,
        use_mort=False,
        use_admn=False,
        use_los=False,
    ) -> pd.DataFrame:
        """Handles logic for creating the labelled cohort based on arguments passed to extract().

        Parameters:
        df: dataframe with patient data
        gap: specified time interval gap for readmissions
        group_col: patient identifier to group patients (normally subject_id)
        visit_col: visit identifier for individual patient visits (normally hadm_id or stay_id)
        admit_col: column for visit start date information (normally admittime or intime)
        disch_col: column for visit end date information (normally dischtime or outtime)
        valid_col: generated column containing a patient's year that corresponds to the 2017-2019 anchor time range
        dod_col: Date of death column
        """

        case = None  # hadm_ids with readmission within the gap period
        ctrl = None  # hadm_ids without readmission within the gap period
        invalid = None  # hadm_ids that are not considered in the cohort
        if use_mort:
            return self.partition_by_mort(
                df, group_col, visit_col, admit_col, disch_col, death_col
            )
        elif use_admn:
            gap = datetime.timedelta(days=gap)
            # transform gap into a timedelta to compare with datetime columns
            case, ctrl, invalid = self.partition_by_readmit(
                df, gap, group_col, visit_col, admit_col, disch_col, valid_col
            )

            # case hadm_ids are labelled 1 for readmission, ctrls have a 0 label
            case["label"] = np.ones(case.shape[0]).astype(int)
            ctrl["label"] = np.zeros(ctrl.shape[0]).astype(int)

            return pd.concat([case, ctrl], axis=0), invalid
        elif use_los:
            return self.partition_by_los(
                df, gap, group_col, visit_col, admit_col, disch_col, death_col
            )

    def extract(self) -> None:
        if self.use_icu == "ICU":
            visit_col = "stay_id"
            admit_col = "intime"
            disch_col = "outtime"
            # adm_visit_col = "hadm_id"
        else:
            visit_col = "hadm_id"
            admit_col = "admittime"
            disch_col = "dischtime"

        logger.info("===========MIMIC-IV v2.0============")
        self.fill_outputs()
        logger.info(self.log_extracting_for())
        visits = self.load_visits()

        visits_cols = []
        if self.use_icu == "ICU":
            visits_cols = [
                "subject_id",
                "stay_id",
                "hadm_id",
                "intime",
                "outtime",
                "los",
            ]
        else:
            visits_cols = ["subject_id", "hadm_id", "admittime", "dischtime", "los"]
        visits = visits[visits_cols]

        patients = self.load_patients()
        patients_cols = [
            "subject_id",
            "anchor_year",
            "anchor_age",
            "yob",
            "min_valid_year",
            "dod",
            "gender",
        ]
        patients = patients[patients_cols]
        visits_patients = visits.merge(
            patients, how="inner", left_on="subject_id", right_on="subject_id"
        )
        visits_patients["Age"] = visits_patients["anchor_age"]
        visits_patients = visits_patients.loc[visits_patients["Age"] >= 18]
        ##Add Demo data
        eth = self.load_hosp_admissions()[["hadm_id", "insurance", "race"]]
        visits_patients = visits_patients.merge(
            eth, how="inner", left_on="hadm_id", right_on="hadm_id"
        )

        if self.use_icu == "ICU":
            visits_patients = visits_patients[
                [
                    "subject_id",
                    visit_col,
                    "hadm_id",
                    admit_col,
                    disch_col,
                    "los",
                    "min_valid_year",
                    "dod",
                    "Age",
                    "gender",
                    "race",
                    "insurance",
                ]
            ]
        else:
            visits_patients = visits_patients.dropna(subset=["min_valid_year"])[
                [
                    "subject_id",
                    visit_col,
                    admit_col,
                    disch_col,
                    "los",
                    "min_valid_year",
                    "dod",
                    "Age",
                    "gender",
                    "race",
                    "insurance",
                ]
            ]

        if self.label == "Mortality":
            cohort, invalid = self.get_case_ctrls(
                visits_patients,
                None,
                "subject_id",
                visit_col,
                admit_col,
                disch_col,
                "min_valid_year",
                "dod",
                use_mort=True,
                use_admn=False,
                use_los=False,
            )
        elif self.label == "Readmission":
            interval = self.time
            cohort, invalid = self.get_case_ctrls(
                visits_patients,
                interval,
                "subject_id",
                visit_col,
                admit_col,
                disch_col,
                "min_valid_year",
                "dod",
                use_mort=False,
                use_admn=True,
                use_los=False,
            )
        elif self.label == "Length of Stay":
            cohort, invalid = self.get_case_ctrls(
                visits_patients,
                self.time,
                "subject_id",
                visit_col,
                admit_col,
                disch_col,
                "min_valid_year",
                "dod",
                use_mort=False,
                use_admn=False,
                use_los=True,
            )
        if self.icd_code != "No Disease Filter":
            hids = disease_cohort.extract_diag_cohort(
                cohort["hadm_id"], self.icd_code, self.raw_dir
            )
            cohort = cohort[cohort["hadm_id"].isin(hids["hadm_id"])]
            self.cohort_output = self.cohort_output + "_" + self.icd_code
            self.summary_output = self.summary_output + "_" + self.icd_code
        # save output
        cohort = cohort.rename(columns={"race": "ethnicity"})

        # cohort[cols].to_csv(
        #     root_dir + "/data/cohort/" + cohort_output + ".csv.gz",
        #     index=False,
        #     compression="gzip",
        # )
        logger.info("[ COHORT SUCCESSFULLY SAVED ]")
        logger.info(self.cohort_output)
        return cohort
