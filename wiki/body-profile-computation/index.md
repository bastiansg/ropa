# Body Profile Computation

The body profile is computed from a known body height, 2D anatomical keypoints, and
person-segmentation masks for the four [available body views](available-views.md).
The computation does not require a reconstructed mesh.

## Anatomical registration

Each view has its own image coordinate system. The midpoint of the left and right
hip keypoints defines the hip center, while the midpoint of the left and right
acromion keypoints defines the shoulder center. The line from the hip center to
the shoulder center is the longitudinal torso axis. A normalized torso level is
measured along this axis:

- `0` is the hip-joint level.
- `1` is the shoulder level.

The same normalized level is converted independently into image coordinates in
each view. Consequently, the front width and side depth used for a circumference
come from the same relative anatomical height even when the person has a
different position, size, or slight tilt between photographs.

Silhouette cross-sections are taken perpendicular to the torso axis. Only the
continuous segment of the person mask nearest the torso center is retained. This
prevents detached hands, the other leg, and isolated segmentation noise from
becoming part of a measurement.

## Image scale

The supplied height establishes the absolute scale. The relaxed front and relaxed
side masks provide their respective head-to-foot pixel heights. Their centimeters
per pixel are transferred to the extended-arm front and raised-arms side views by
comparing hip-to-shoulder keypoint distances within each orientation.

This transfer is necessary for the raised-arms side photograph: its complete mask
extends from the feet to the raised hands and therefore cannot be interpreted as
the person's standing height.

## Circumference model

At every candidate anatomical level, the extended-arm front mask supplies the
transverse diameter and the raised-arms side mask supplies the depth diameter.
The two diameters form an elliptical cross-section. Its circumference is
approximated with Ramanujan's second ellipse formula.

Candidate circumference curves are median-smoothed across five neighboring
samples before an anatomical level is selected. This reduces sensitivity to a
single irregular mask row, clothing fold, or noisy keypoint.

### Chest circumference

The chest is searched between normalized torso levels `0.55` and `0.74`, below
the extended arms and above the waist. A front cross-section is rejected when it
exceeds twice the distance between the left and right acromion keypoints;
such a span contains the arms rather than only the torso. Among the remaining
candidates, the level with the greatest smoothed combined front-and-side
circumference is selected. The final value uses the front width and side depth at
that shared level.

### Waist circumference

The waist is searched between normalized torso levels `0.20` and `0.55`. The
level with the smallest smoothed combined circumference is selected. The waist
therefore retains the same anatomical meaning for every body; a prominent
abdomen does not cause the computation to substitute an abdominal circumference.

### Hip circumference

The hip or seat is searched between normalized torso levels `-0.18` and `0.15`,
covering the area immediately below and above the hip-joint keypoints. The level
with the greatest smoothed combined circumference is selected.

### Neck circumference

The neck keypoint is projected onto the torso axis in the relaxed front and
relaxed side views. A narrow band of `0.08` torso lengths on either side of the
mean projected level is searched. Because hair belongs to the person mask and can
hide the actual neck boundary, the cross-sections are restricted by head
keypoints: the relaxed-front radius is `0.375` times the projected distance
between the ears, and the relaxed-side radius is `0.6` times the projected
distance from the midpoint of the ears to the nose. The mask must occupy the
bounded cross-section, but hair outside it cannot enlarge the measurement. The
smallest smoothed circumference combines the resulting relaxed-front width and
relaxed-side depth.

## Linear measurements

### Height

Height is supplied as an input rather than inferred. The relaxed-front mask shows
the head-to-foot line used to establish its image scale and measurement guide.

### Shoulder width

Shoulder width is measured in the relaxed front view at the mean vertical level
of the left and right acromion keypoints. The person-mask span is restricted to
the interval between those keypoints and converted with the relaxed-front scale.

### Arm sleeve length

The relaxed front view supplies one polyline per arm, running from acromion to
elbow to wrist. Their scaled lengths are averaged to reduce pose and keypoint
asymmetry.

### Leg length

The relaxed front view supplies one polyline per leg, running from hip to knee to
ankle. Their scaled lengths are averaged.

### Foot length

The relaxed side view supplies the heel and the big- and small-toe-tip keypoints
for both feet. At their mean vertical position, the person-mask span is restricted
to the horizontal keypoint bounds and converted with the relaxed-side scale.

## Measurement views

| Measurement | Transverse or primary view | Depth view |
| --- | --- | --- |
| Chest circumference | Extended-arm front | Raised-arms side |
| Waist circumference | Extended-arm front | Raised-arms side |
| Hip circumference | Extended-arm front | Raised-arms side |
| Neck circumference | Relaxed front | Relaxed side |
| Height | Relaxed front | — |
| Shoulder width | Relaxed front | — |
| Arm sleeve length | Relaxed front | — |
| Leg length | Relaxed front | — |
| Foot length | Relaxed side | — |

## Related reference

- [Available body views](available-views.md)
