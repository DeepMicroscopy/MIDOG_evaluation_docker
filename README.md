
![image](https://user-images.githubusercontent.com/10051592/130207467-6a49b4e5-1740-4bd8-8fcb-5228b651c6c4.png)

# MIDOG_evaluation_docker

Evaluation container for the MIDOG 2021 challenge on grand-challenge.org. This container is losely based on the evalutils-created evaluation container from grand-challenge.org, yet is utilizes new (so far undocumented) interfaces. 

This container is provided for transparency reasons and to improve clarity of evaluation for the participants. 

# Inputs
The grand-challenge.org system provides a file /input/predictions.json to the container, esentially consisting of a list of dictionaries where each dictionary contains the results of a single image (and thus a single docker container run). 

# Outputs
The container provides detailed outputs for each image as well as the overall F1 score, precision and recall.

> {
>    "case": {
>        "007.tiff": {
>            "true_positives": 2,
>            "false_negatives": 0,
>            "false_positives": 1
>        }
>    },
>    "aggregates": {
>        "precision": 0.6666666666666666,
>        "recall": 1.0,
>        "f1_score": 0.8
>    }
> }
