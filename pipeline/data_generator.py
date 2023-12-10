import numpy as np
import pandas as pd
from tqdm import tqdm
import pickle
import os
from pipeline.feature.lab_events import Lab
from pipeline.feature.medications import Medications
from pipeline.feature.output_events import OutputEvents
from pipeline.feature.procedures import Procedures
from pipeline.file_info.preproc.cohort import COHORT_PATH
from pipeline.prediction_task import PredictionTask, TargetType
import logging

from pipeline.features_extractor import FeatureExtractor
from pipeline.feature.chart_events import ChartEvents
from pipeline.feature.diagnoses import Diagnoses
from pipeline.preprocessing.cohort import read_cohort
from pipeline.file_info.preproc.cohort import (
    CohortHeader,
    NonIcuCohortHeader,
    IcuCohortHeader,
)

logger = logging.getLogger()


class DataGenerator:
    def __init__(
        self,
        use_icu: bool,
        cohort_output: pd.DataFrame,
        feature_extractor: FeatureExtractor,
        prediction_task: PredictionTask,
        impute: str,
        include_time: int = 24,
        bucket: int = 1,
        predW: int = 0,
    ):
        self.cohort_output = cohort_output
        self.use_icu = use_icu
        self.feature_extractor = feature_extractor
        self.prediction_task = prediction_task
        self.impute = impute
        self.include_time = include_time
        self.bucket = bucket
        self.predW = predW

    def generate(self):
        self.data = read_cohort(self.cohort_output, self.use_icu)
        features = []
        if self.feature_extractor.for_diagnoses:
            dia = Diagnoses(
                cohort=pd.DataFrame(),
                use_icu=self.feature_extractor.use_icu,
            )
            features.append(dia.generate_fun())
            print("[ ======READING DIAGNOSIS ]")
        if self.feature_extractor.for_procedures:
            print("[ ======READING PROCEDURES ]")
            proc = Procedures(
                cohort=pd.DataFrame(), use_icu=self.feature_extractor.use_icu
            )
            features.append(proc.generate_fun())
        if self.feature_extractor.for_medications:
            print("[ ======READING MEDICATIONS ]")
            med = Medications(
                cohort=pd.DataFrame(), use_icu=self.feature_extractor.use_icu
            )
            features.append(med.generate_fun())
        if self.feature_extractor.for_labs:
            print("[ ======READING LABS ]")
            labs = Lab()
            features.append(labs.generate_fun())

        if self.feature_extractor.for_labs:
            print("[ ======READING LABS ]")
            out = OutputEvents(cohort=pd.DataFrame())
            features.append(out.generate_fun())

        return

    # def process_data(self):

    #     print("[ READ ALL FEATURES ]")
    #     if self.prediction_task.target_type == TargetType.MORTALITY:
    #         print(self.predW)
    #         mortality_length(self.cohort, self.include_time, self.predW)
    #         print("[ PROCESSED TIME SERIES TO EQUAL LENGTH  ]")
    #     elif self.prediction_task.target_type == TargetType.READMISSION:
    #         self.readmission_length(self.include_time)
    #         print("[ PROCESSED TIME SERIES TO EQUAL LENGTH  ]")
    #     elif self.prediction_task.target_type == TargetType.LOS:
    #         self.los_length(self.include_time)
    #         print("[ PROCESSED TIME SERIES TO EQUAL LENGTH  ]")
    #     self.smooth_meds(self.bucket)
    #     print("[ SUCCESSFULLY SAVED DATA DICTIONARIES ]")

    # def smooth_meds(self, bucket):
    #     final_meds = pd.DataFrame()
    #     final_proc = pd.DataFrame()
    #     final_labs = pd.DataFrame()

    #     if self.feat_med:
    #         self.meds = self.meds.sort_values(by=["start_time"])
    #     if self.feat_proc:
    #         self.proc = self.proc.sort_values(by=["start_time"])

    #     t = 0
    #     for i in tqdm(range(0, self.los, bucket)):
    #         ###MEDS
    #         if self.feat_med:
    #             sub_meds = (
    #                 self.meds[
    #                     (self.meds["start_time"] >= i)
    #                     & (self.meds["start_time"] < i + bucket)
    #                 ]
    #                 .groupby(["hadm_id", "drug_name"])
    #                 .agg(
    #                     {
    #                         "stop_time": "max",
    #                         "subject_id": "max",
    #                         "dose_val_rx": np.nanmean,
    #                     }
    #                 )
    #             )
    #             sub_meds = sub_meds.reset_index()
    #             sub_meds["start_time"] = t
    #             sub_meds["stop_time"] = sub_meds["stop_time"] / bucket
    #             if final_meds.empty:
    #                 final_meds = sub_meds
    #             else:
    #                 final_meds = pd.concat([final_meds, sub_meds], ignore_index=True)

    #         ###PROC
    #         if self.feat_proc:
    #             sub_proc = (
    #                 self.proc[
    #                     (self.proc["start_time"] >= i)
    #                     & (self.proc["start_time"] < i + bucket)
    #                 ]
    #                 .groupby(["hadm_id", "icd_code"])
    #                 .agg({"subject_id": "max"})
    #             )
    #             sub_proc = sub_proc.reset_index()
    #             sub_proc["start_time"] = t
    #             if final_proc.empty:
    #                 final_proc = sub_proc
    #             else:
    #                 final_proc = pd.concat([final_proc, sub_proc], ignore_index=True)

    #         ###LABS
    #         if self.feat_lab:
    #             sub_labs = (
    #                 self.labs[
    #                     (self.labs["start_time"] >= i)
    #                     & (self.labs["start_time"] < i + bucket)
    #                 ]
    #                 .groupby(["hadm_id", "itemid"])
    #                 .agg({"subject_id": "max", "valuenum": np.nanmean})
    #             )
    #             sub_labs = sub_labs.reset_index()
    #             sub_labs["start_time"] = t
    #             if final_labs.empty:
    #                 final_labs = sub_labs
    #             else:
    #                 final_labs = pd.concat([final_labs, sub_labs], ignore_index=True)

    #         t = t + 1
    #     los = int(self.los / bucket)

    #     ###MEDS
    #     if self.feat_med:
    #         f2_meds = final_meds.groupby(["hadm_id", "drug_name"]).size()
    #         self.med_per_adm = f2_meds.groupby("hadm_id").sum().reset_index()[0].max()
    #         self.medlength_per_adm = final_meds.groupby("hadm_id").size().max()

    #     ###PROC
    #     if self.feat_proc:
    #         f2_proc = final_proc.groupby(["hadm_id", "icd_code"]).size()
    #         self.proc_per_adm = f2_proc.groupby("hadm_id").sum().reset_index()[0].max()
    #         self.proclength_per_adm = final_proc.groupby("hadm_id").size().max()

    #     ###LABS
    #     if self.feat_lab:
    #         f2_labs = final_labs.groupby(["hadm_id", "itemid"]).size()
    #         self.labs_per_adm = f2_labs.groupby("hadm_id").sum().reset_index()[0].max()
    #         self.labslength_per_adm = final_labs.groupby("hadm_id").size().max()

    #     ###CREATE DICT
    #     print("[ PROCESSED TIME SERIES TO EQUAL TIME INTERVAL ]")
    #     self.create_Dict(final_meds, final_proc, final_labs, los)

    # def create_Dict(self, meds, proc, labs, los):
    #     print("[ CREATING DATA DICTIONARIES ]")
    #     dataDic = self.initialize_dataDic()
    #     labels_csv = self.initialize_labels_csv()

    #     for hid in tqdm(self.hids):
    #         self.process_individual_hid(hid, dataDic, labels_csv, meds, proc, labs, los)

    #     self.save_dictionaries(dataDic)
    #     labels_csv.to_csv("./data/csv/labels.csv", index=False)

    # def initialize_labels_csv(self):
    #     labels_csv = pd.DataFrame(columns=["hadm_id", "label"])
    #     labels_csv["hadm_id"] = pd.Series(self.hids)
    #     labels_csv["label"] = 0
    #     return labels_csv

    # def process_individual_hid(self, hid, dataDic, labels_csv, meds, proc, labs, los):
    #     # Method implementation (process for each hadm_id)
    #     # Update dataDic and labels_csv inside this method
    #     # This method will contain the core of your original for loop
    #     grp = self.data[self.data["hadm_id"] == hid]
    #     dataDic[hid] = {
    #         "Cond": {},
    #         "Proc": {},
    #         "Med": {},
    #         "Lab": {},
    #         "ethnicity": grp["ethnicity"].iloc[0],
    #         "age": int(grp["Age"]),
    #         "gender": grp["gender"].iloc[0],
    #         "label": int(grp["label"]),
    #     }
    #     labels_csv.loc[labels_csv["hadm_id"] == hid, "label"] = int(grp["label"])
    #     demo_csv = grp[["Age", "gender", "ethnicity", "insurance"]]
    #     if not os.path.exists("./data/csv/" + str(hid)):
    #         os.makedirs("./data/csv/" + str(hid))
    #     demo_csv.to_csv("./data/csv/" + str(hid) + "/demo.csv", index=False)

    #     dyn_csv = pd.DataFrame()
    #     ###MEDS
    #     if self.feat_med:
    #         feat = meds["drug_name"].unique()
    #         df2 = meds[meds["hadm_id"] == hid]
    #         if df2.shape[0] == 0:
    #             val = pd.DataFrame(np.zeros([los, len(feat)]), columns=feat)
    #             val = val.fillna(0)
    #             val.columns = pd.MultiIndex.from_product([["MEDS"], val.columns])
    #         else:
    #             val = df2.pivot_table(
    #                 index="start_time", columns="drug_name", values="dose_val_rx"
    #             )
    #             df2 = df2.pivot_table(
    #                 index="start_time", columns="drug_name", values="stop_time"
    #             )
    #             # print(df2.shape)
    #             add_indices = pd.Index(range(los)).difference(df2.index)
    #             add_df = pd.DataFrame(index=add_indices, columns=df2.columns).fillna(
    #                 np.nan
    #             )
    #             df2 = pd.concat([df2, add_df])
    #             df2 = df2.sort_index()
    #             df2 = df2.ffill()
    #             df2 = df2.fillna(0)

    #             val = pd.concat([val, add_df])
    #             val = val.sort_index()
    #             val = val.ffill()
    #             val = val.fillna(-1)
    #             # print(df2.head())
    #             df2.iloc[:, 0:] = df2.iloc[:, 0:].sub(df2.index, 0)
    #             df2[df2 > 0] = 1
    #             df2[df2 < 0] = 0
    #             val.iloc[:, 0:] = df2.iloc[:, 0:] * val.iloc[:, 0:]
    #             # print(df2.head())
    #             dataDic[hid]["Med"]["signal"] = df2.iloc[:, 0:].to_dict(orient="list")
    #             dataDic[hid]["Med"]["val"] = val.iloc[:, 0:].to_dict(orient="list")

    #             feat_df = pd.DataFrame(columns=list(set(feat) - set(val.columns)))

    #             val = pd.concat([val, feat_df], axis=1)

    #             val = val[feat]
    #             val = val.fillna(0)

    #             val.columns = pd.MultiIndex.from_product([["MEDS"], val.columns])
    #         if dyn_csv.empty:
    #             dyn_csv = val
    #         else:
    #             dyn_csv = pd.concat([dyn_csv, val], axis=1)

    #         ###PROCS

    #     if self.feat_proc:
    #         feat = proc["icd_code"].unique()
    #         df2 = proc[proc["hadm_id"] == hid]
    #         if df2.shape[0] == 0:
    #             df2 = pd.DataFrame(np.zeros([los, len(feat)]), columns=feat)
    #             df2 = df2.fillna(0)
    #             df2.columns = pd.MultiIndex.from_product([["PROC"], df2.columns])
    #         else:
    #             df2["val"] = 1
    #             df2 = df2.pivot_table(
    #                 index="start_time", columns="icd_code", values="val"
    #             )
    #             # print(df2.shape)
    #             add_indices = pd.Index(range(los)).difference(df2.index)
    #             add_df = pd.DataFrame(index=add_indices, columns=df2.columns).fillna(
    #                 np.nan
    #             )
    #             df2 = pd.concat([df2, add_df])
    #             df2 = df2.sort_index()
    #             df2 = df2.fillna(0)
    #             df2[df2 > 0] = 1
    #             # print(df2.head())
    #             dataDic[hid]["Proc"] = df2.to_dict(orient="list")

    #             feat_df = pd.DataFrame(columns=list(set(feat) - set(df2.columns)))
    #             df2 = pd.concat([df2, feat_df], axis=1)

    #             df2 = df2[feat]
    #             df2 = df2.fillna(0)
    #             df2.columns = pd.MultiIndex.from_product([["PROC"], df2.columns])

    #         if dyn_csv.empty:
    #             dyn_csv = df2
    #         else:
    #             dyn_csv = pd.concat([dyn_csv, df2], axis=1)

    #     ###LABS
    #     if self.feat_lab:
    #         feat = labs["itemid"].unique()
    #         df2 = labs[labs["hadm_id"] == hid]
    #         if df2.shape[0] == 0:
    #             val = pd.DataFrame(np.zeros([los, len(feat)]), columns=feat)
    #             val = val.fillna(0)
    #             val.columns = pd.MultiIndex.from_product([["LAB"], val.columns])
    #         else:
    #             val = df2.pivot_table(
    #                 index="start_time", columns="itemid", values="valuenum"
    #             )
    #             df2["val"] = 1
    #             df2 = df2.pivot_table(
    #                 index="start_time", columns="itemid", values="val"
    #             )
    #             # print(df2.shape)
    #             add_indices = pd.Index(range(los)).difference(df2.index)
    #             add_df = pd.DataFrame(index=add_indices, columns=df2.columns).fillna(
    #                 np.nan
    #             )
    #             df2 = pd.concat([df2, add_df])
    #             df2 = df2.sort_index()
    #             df2 = df2.fillna(0)

    #             val = pd.concat([val, add_df])
    #             val = val.sort_index()
    #             if self.impute == "Mean":
    #                 val = val.ffill()
    #                 val = val.bfill()
    #                 val = val.fillna(val.mean())
    #             elif self.impute == "Median":
    #                 val = val.ffill()
    #                 val = val.bfill()
    #                 val = val.fillna(val.median())
    #             val = val.fillna(0)

    #             df2[df2 > 0] = 1
    #             df2[df2 < 0] = 0

    #             # print(df2.head())
    #             dataDic[hid]["Lab"]["signal"] = df2.iloc[:, 0:].to_dict(orient="list")
    #             dataDic[hid]["Lab"]["val"] = val.iloc[:, 0:].to_dict(orient="list")

    #             feat_df = pd.DataFrame(columns=list(set(feat) - set(val.columns)))
    #             val = pd.concat([val, feat_df], axis=1)

    #             val = val[feat]
    #             val = val.fillna(0)
    #             val.columns = pd.MultiIndex.from_product([["LAB"], val.columns])

    #         if dyn_csv.empty:
    #             dyn_csv = val
    #         else:
    #             dyn_csv = pd.concat([dyn_csv, val], axis=1)

    #     # Save temporal data to csv
    #     dyn_csv.to_csv("./data/csv/" + str(hid) + "/dynamic.csv", index=False)

    #     ##########COND#########
    #     if self.feat_cond:
    #         feat = self.cond["new_icd_code"].unique()
    #         grp = self.cond[self.cond["hadm_id"] == hid]
    #         if grp.shape[0] == 0:
    #             dataDic[hid]["Cond"] = {"fids": list(["<PAD>"])}
    #             feat_df = pd.DataFrame(np.zeros([1, len(feat)]), columns=feat)
    #             grp = feat_df.fillna(0)
    #             grp.columns = pd.MultiIndex.from_product([["COND"], grp.columns])
    #         else:
    #             dataDic[hid]["Cond"] = {"fids": list(grp["new_icd_code"])}
    #             grp["val"] = 1
    #             grp = grp.drop_duplicates()
    #             grp = grp.pivot(
    #                 index="hadm_id", columns="new_icd_code", values="val"
    #             ).reset_index(drop=True)
    #             feat_df = pd.DataFrame(columns=list(set(feat) - set(grp.columns)))
    #             grp = pd.concat([grp, feat_df], axis=1)
    #             grp = grp.fillna(0)
    #             grp = grp[feat]
    #             grp.columns = pd.MultiIndex.from_product([["COND"], grp.columns])
    #     grp.to_csv("./data/csv/" + str(hid) + "/static.csv", index=False)
    #     labels_csv.to_csv("./data/csv/labels.csv", index=False)

    # def save_dictionaries(self, dataDic, meds, proc, labs, los):
    #     self.metaDic = {"Cond": {}, "Proc": {}, "Med": {}, "Lab": {}, "LOS": los}

    #     self._save_pickle("./data/dict/dataDic", dataDic)
    #     self._save_pickle("./data/dict/hadmDic", self.hids)
    #     self._save_feature_vocabularies(meds, proc, labs)

    #     self._save_pickle("./data/dict/metaDic", self.metaDic)

    # def _save_pickle(self, filepath, data):
    #     with open(filepath, "wb") as fp:
    #         pickle.dump(data, fp)

    # def _save_feature_vocabularies(self, meds, proc, labs):
    #     for feature_name, dataset in {
    #         "eth": self.data["ethnicity"],
    #         "age": self.data["Age"],
    #         "ins": self.data["insurance"],
    #     }.items():
    #         vocab = list(dataset.unique())
    #         self._save_pickle(f"./data/dict/{feature_name}Vocab", vocab)
    #         setattr(self, feature_name + "_vocab", len(vocab))

    #     feature_datasets = {
    #         "med": (meds, "drug_name"),
    #         "cond": (self.cond, "new_icd_code"),
    #         "proc": (proc, "icd_code"),
    #         "lab": (labs, "itemid"),
    #     }

    #     for feature, (dataset, column) in feature_datasets.items():
    #         if getattr(self, f"feat_{feature}"):
    #             vocab = list(dataset[column].unique())
    #             self._save_pickle(f"./data/dict/{feature}Vocab", vocab)
    #             setattr(self, feature + "_vocab", len(vocab))
    #             self.metaDic[feature.capitalize()] = getattr(
    #                 self, f"{feature}_per_adm", {}
    #             )
