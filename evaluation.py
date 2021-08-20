from evalutils import DetectionEvaluation
from evalutils.io import FileLoader
from evalutils.validators import ExpectedColumnNamesValidator
import json
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
        self.load_gt()
            
    def load_gt(self):
        self.gt = json.load(open(self._gt_file,'r'))
        
    def load_predictions(self):
        predictions_json = json.load(open(self._predictions_file,'r'))
        predictions={}
        for k in range(len(predictions_json)):
            # predictions[k]['outputs'][...]['image']['name'] contains input image
            # predictions[k]['outputs'][...]['value']  contains value of mitotic-figures.json
            fname = [civ['image']['name'] for civ in predictions_json[k]['inputs'] if civ['interface']['slug'] == 'generic-medical-image'][0]

            if (fname not in self.gt):
                print('Warning: Found predictions for image ',fname,'which is not part of the ground truth.')
                continue
            pred = [civ['value'] for civ in predictions_json[k]['outputs'] if civ['interface']['slug'] == 'mitotic-figures']

            if len(pred)>0:
                if 'points' not in pred[0]:
                    print('Warning: Wrong format. Field points is not part of detections.')
                    continue
                points=[]
                for point in pred[0]['points']:
                    if 'point' not in point:
                        print('Warning: Point is not part of points structure.')
                        continue
                    points.append(point['point'])
                predictions[fname]=points
            else:
                print('Warning: no predictions found for ',fname)
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
            sc = score_detection(ground_truth=self.gt[case],predictions=self.predictions[case],radius=7.5E-3)._asdict()
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

        tp,fp,fn = 0,0,0
        for s in self._case_results:
            tp += self._case_results[s]["true_positives"]            
            fp += self._case_results[s]["false_positives"]            
            fn += self._case_results[s]["false_negatives"]            
        aggregate_results=dict()

        aggregate_results["precision"] = tp / (tp + fp)
        aggregate_results["recall"] = tp / (tp + fn)
        aggregate_results["f1_score"] = 2 * tp / ((2 * tp) + fp + fn)

        return aggregate_results


if __name__ == "__main__":
    MIDOG2021Evaluation().evaluate()
