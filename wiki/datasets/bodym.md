---
type: Dataset
title: BodyM Training Dataset
description: The downloaded BodyM training data, its local layout, schema, and upstream provenance.
resource: ../../resources/datasets/bodym/
tags:
  - body-measurement
  - training-data
  - silhouettes
sources:
  - id: aws-registry
    title: BodyM Dataset — Registry of Open Data on AWS
    url: https://registry.opendata.aws/bodym/
  - id: bodym-paper
    title: Human Body Measurement Estimation with Adversarial Augmentation
    url: https://arxiv.org/abs/2210.05667
---

# BodyM Training Dataset

BodyM is a public research dataset pairing frontal and lateral human silhouettes with height, weight, gender, and 14 body measurements. The complete AWS release contains 8,978 silhouettes for 2,505 subjects and is divided into training, Test-A, and Test-B sets.[^aws-registry]

The dataset was introduced with BMnet, a network that estimates body measurements from two silhouettes plus height and weight. Its measurements were derived from registered 3D body scans. The authors released silhouettes rather than the source RGB photographs to reduce disclosure of subject identity.[^bodym-paper]

## Local training data

Only training data is present at `resources/datasets/bodym/train/`. Counts below describe the downloaded files, not the complete upstream release.

| Artifact | Local path | Contents | Local count |
| --- | --- | --- | ---: |
| Subject metadata | `hwg_metadata.csv` | `subject_id`, gender, height in cm, and weight in kg | 2,018 subjects |
| Body measurements | `measurements.csv` | `subject_id` and 14 measurements in cm | 2,018 subjects |
| Photo map | `subject_to_photo_map.csv` | Subject-to-photo relationships | 6,134 photo IDs |
| Frontal masks | `mask/<photo_id>.png` | 720×960 grayscale silhouette masks | 6,134 images |
| Left-side masks | `mask_left/<photo_id>.png` | 720×960 grayscale silhouette masks | 6,134 images |

All three CSV files use `subject_id` as the subject-level join key. `subject_to_photo_map.csv` associates each subject with one or more `photo_id` values; that value is the filename stem shared by its frontal and left-side masks.

## Measurement columns

`measurements.csv` contains the following measurements, all in centimeters:[^aws-registry]

- `ankle`: ankle girth
- `arm-length`: arm length
- `bicep`: bicep girth
- `calf`: calf girth
- `chest`: chest girth
- `forearm`: forearm girth
- `height`: head-to-heel length
- `hip`: hip girth
- `leg-length`: leg length
- `shoulder-breadth`: shoulder breadth
- `shoulder-to-crotch`: shoulder-to-crotch length
- `thigh`: thigh girth
- `waist`: waist girth
- `wrist`: wrist girth

`hwg_metadata.csv` separately records `height_cm`. Keep the two height fields distinct: `height_cm` is supplied subject metadata, while `height` belongs to the set of measurements derived from the registered body mesh.[^bodym-paper]

## Capture conditions and intended use

Training and Test-A subjects were photographed and scanned under technician-controlled lab conditions. Test-B uses lab scans but less-controlled photographs with varied camera orientation and lighting. Some subjects have multiple captures in different clothing.[^aws-registry] The locally downloaded directory contains no Test-A or Test-B files.

The BodyM paper cautions that body measurements are confidential attributes and that rare, high-BMI shapes are under-represented in the training data. Models trained on this data should therefore be evaluated for privacy, access control, and performance across body-shape distributions.[^bodym-paper]

## Upstream access and license

AWS hosts the dataset in the public `amazon-bodym` S3 bucket in `us-west-2`; it can be listed without an AWS account:

```console
aws s3 ls --no-sign-request s3://amazon-bodym/
```

The AWS registry labels the dataset “Creative Commons Attribution-Non Commercial 4.0 International,” but its displayed legal-code link currently points to the CC BY 4.0 text rather than CC BY-NC 4.0.[^aws-registry] Confirm the governing license with the dataset owner before redistribution or commercial use.

When citing the data, follow the AWS registry's requested access citation and cite the accompanying paper.[^aws-registry]

[^aws-registry]: [BodyM Dataset — Registry of Open Data on AWS](https://registry.opendata.aws/bodym/)
[^bodym-paper]: [Ruiz et al., “Human Body Measurement Estimation with Adversarial Augmentation” (2022)](https://arxiv.org/abs/2210.05667)
