from evalutils import DetectionEvaluation
from evalutils.io import FileLoader
from evalutils.validators import ExpectedColumnNamesValidator
from torchmetrics.detection.mean_ap import MeanAveragePrecision
import json
from torch import Tensor
import numpy as np
import urllib
from pandas import read_json
from evalutils.scorers import score_detection 

from typing import Dict

class MIDOG2021Evaluation():
    
    def __init__(self,predictions_file = '/input/predictions.json', 
                      gt_file='/opt/evaluation/ground-truth/ground-truth.json',
                      output_file='/output/metrics.json'):
        self._predictions_file = predictions_file
        self._gt_file = gt_file
        self._output_file = output_file
        self.map_metric = MeanAveragePrecision(box_format='xyxy', iou_type='bbox', max_detection_thresholds=[1,10,1e6], rec_thresholds=np.arange(0,1.01,0.01).tolist())
        self.load_gt()

        self.tumor_case_stepping=10
        self.total_cases = 100
        self.case_to_tumor = {'%03d.tiff' % (d+1) : int(d/self.tumor_case_stepping) for d in range(self.total_cases)}
        self.per_tumor_map_metric = {d : MeanAveragePrecision(box_format='xyxy', iou_type='bbox', max_detection_thresholds=[1,10,1e6], rec_thresholds=np.arange(0,1.01,0.01).tolist()) for d in range(int(self.total_cases/self.tumor_case_stepping))}

    def load_gt(self):
        self.gt = json.load(open(self._gt_file,'r'))
        
    def load_predictions(self):
        predictions_json = json.load(open(self._predictions_file,'r'))
        predictions={}
        for k in range(len(predictions_json)):
            # predictions[k]['outputs'][...]['image']['name'] contains input image
            # predictions[k]['outputs'][...]['value']  contains value of mitotic-figures.json
            fname = [civ['image']['name'] for civ in predictions_json[k]['inputs'] if civ['interface']['slug'] == 'histopathology-region-of-interest-cropout'][0]

            if (fname not in self.gt):
                print('Warning: Found predictions for image ',fname,'which is not part of the ground truth.')
                continue
            #pred = [civ['value'] for civ in predictions_json[k]['outputs'] if civ['interface']['slug'] == 'mitotic-figures']

            # retrieve detections via Rest API
            fileu = predictions_json[k]['outputs'][0]['file']
            pk = predictions_json[k]['pk']
            relative_path = predictions_json[k]['outputs'][0]['interface']['relative_path']

            with open(f'/input/{pk}/output/{relative_path}') as response:
                 pred = json.load(response)

            if pred is None:
                    continue
            if 'points' not in pred:
                    print('Warning: Wrong format. Field points is not part of detections.')
                    continue
            points=[]

            for point in pred['points']:
                    detected_class = 1 if 'name' not in point or point['name']=='mitotic figure' else 0
                    detected_thr   = 0.5 if 'probability' not in point else point['probability']

                    if 'name' not in point:
                        print('Warning: Old format. Field name is not part of detections.')

                    if 'probability' not in point:
                        print('Warning: Old format. Field probability is not part of detections.')
                    
                    if 'point' not in point:
                        print('Warning: Point is not part of points structure.')
                        continue

                    points.append([*point['point'][0:3], detected_class, detected_thr])

            predictions[fname]=points
        self.predictions=predictions

    @property
    def _metrics(self) -> Dict:
        """ Returns the calculated case and aggregate results """
        return {
            "case": self._case_results,
            "aggregates": self._aggregate_results,
        }        
    def score(self):
        cases = list(self.gt.keys())
        self._case_results={}
        for idx, case in enumerate(cases):
            if case not in self.predictions:
                print('Warning: No prediction for file: ',case)
                continue

            # Filter out all predictions with class==0, retain predictions with class==1
            filtered_predictions = [[x,y,0] for x,y,z,cls,sc in self.predictions[case] if cls==1]

            bbox_size = 0.01125 # equals to 7.5mm distance for horizontal distance at 0.5 IOU

            pred_dict = [{'boxes': Tensor([[x-bbox_size,y-bbox_size, x+bbox_size, y+bbox_size] for (x,y,z,_,_) in self.predictions[case]]), 
                         'labels': Tensor([1,]*len(self.predictions[case])),
                         'scores': Tensor([sc for (x,y,z,_,sc) in self.predictions[case]])}]
            target_dict = [{'boxes': Tensor([[x-bbox_size,y-bbox_size, x+bbox_size, y+bbox_size] for (x,y,z) in self.gt[case]]),
                           'labels' : Tensor([1,]*len(self.gt[case]))}]

            self.map_metric.update(pred_dict,target_dict)
            self.per_tumor_map_metric[self.case_to_tumor[case]].update(pred_dict,target_dict)

            sc = score_detection(ground_truth=self.gt[case],predictions=filtered_predictions,radius=7.5E-3)._asdict()
            self._case_results[case] = sc

        self._aggregate_results = self.score_aggregates()

    def save(self):
        with open(self._output_file, "w") as f:
                    f.write(json.dumps(self._metrics))        
    def evaluate(self):
        self.load_predictions()
        self.score()
        self.save()
        
    def score_aggregates(self):


        # per tumor stats
        per_tumor = {d : {'tp': 0, 'fp':0, 'fn':0} for d in self.per_tumor_map_metric}

        tp,fp,fn = 0,0,0
        for s in self._case_results:
            tp += self._case_results[s]["true_positives"]            
            fp += self._case_results[s]["false_positives"]            
            fn += self._case_results[s]["false_negatives"]            

            per_tumor[self.case_to_tumor[s]]['tp'] += self._case_results[s]["true_positives"] 
            per_tumor[self.case_to_tumor[s]]['fp'] += self._case_results[s]["false_positives"] 
            per_tumor[self.case_to_tumor[s]]['fn'] += self._case_results[s]["false_negatives"] 

        aggregate_results=dict()


        eps = 1E-6

        aggregate_results["precision"] = tp / (tp + fp + eps)
        aggregate_results["recall"] = tp / (tp + fn + eps)
        aggregate_results["f1_score"] = (2 * tp + eps) / ((2 * tp) + fp + fn + eps)

        metrics_values = self.map_metric.compute()
        aggregate_results["mAP"] = metrics_values['map_50'].tolist()


        for tumor in per_tumor:
            aggregate_results[f'tumor_{tumor}_precision'] = per_tumor[tumor]['tp'] / (per_tumor[tumor]['tp'] + per_tumor[tumor]['fp'] + eps)
            aggregate_results[f'tumor_{tumor}_recall'] = per_tumor[tumor]['tp'] / (per_tumor[tumor]['tp'] + per_tumor[tumor]['fn'] + eps)
            aggregate_results[f'tumor_{tumor}_f1'] = (2 * per_tumor[tumor]['tp'] + eps) / ((2 * per_tumor[tumor]['tp']) + per_tumor[tumor]['fp'] + per_tumor[tumor]['fn'] + eps) 

            pt_metrics_values = self.per_tumor_map_metric[tumor].compute()
            aggregate_results[f"tumor_{tumor}_mAP"] = pt_metrics_values['map_50'].tolist()


        return aggregate_results


if __name__ == "__main__":
    MIDOG2021Evaluation().evaluate()
