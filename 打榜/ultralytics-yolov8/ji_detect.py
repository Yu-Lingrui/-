import os
import sys
import cv2
import glob
import json
import time
from tqdm import tqdm
import numpy as np

# sys.path.append("/project/train/src_repo/")
import torch
# from utils.torch_utils import select_device
# from utils.augmentations import letterbox
# from utils.general import check_img_size, non_max_suppression, scale_coords
# from models.experimental import attempt_load
from ultralytics import YOLO
from ultralytics.utils import ops
from ultralytics.nn.tasks import  attempt_load_weights


CONF_THRESH = 0.25
IOU_THRESHOLD = 0.45
# CONF_THRESH = 0.5
# IOU_THRESHOLD = 0.45
device = 'cuda:0'
# device = 'cpu'
model_path = '/project/train/models/exp/weights/best.pt'
imgsz = 640
stride = 32
half = True
# half = False
# categories = ["slagcar", "car", "tricar", "motorbike", "bicycle", "bus", "truck", "tractor"]
categories = ['person','head','door_open','door_half_open','door_close','daizi','bottle','bag','box','plastic_basket','suitcase','mobile_phone','umbrella','folder','bicycle','electric_scooter']
target_categories = ['electric_scooter'] 

def letterbox(im, new_shape=(640, 640), color=(114, 114, 114), auto=True, scaleFill=False, scaleup=True, stride=32):
    # Resize and pad image while meeting stride-multiple constraints
    shape = im.shape[:2]  # current shape [height, width]
    if isinstance(new_shape, int):
        new_shape = (new_shape, new_shape)

    # Scale ratio (new / old)
    r = min(new_shape[0] / shape[0], new_shape[1] / shape[1])
    if not scaleup:  # only scale down, do not scale up (for better val mAP)
        r = min(r, 1.0)

    # Compute padding
    ratio = r, r  # width, height ratios
    new_unpad = int(round(shape[1] * r)), int(round(shape[0] * r))
    dw, dh = new_shape[1] - new_unpad[0], new_shape[0] - new_unpad[1]  # wh padding
    if auto:  # minimum rectangle
        dw, dh = np.mod(dw, stride), np.mod(dh, stride)  # wh padding
    elif scaleFill:  # stretch
        dw, dh = 0.0, 0.0
        new_unpad = (new_shape[1], new_shape[0])
        ratio = new_shape[1] / shape[1], new_shape[0] / shape[0]  # width, height ratios

    dw /= 2  # divide padding into 2 sides
    dh /= 2

    if shape[::-1] != new_unpad:  # resize
        im = cv2.resize(im, new_unpad, interpolation=cv2.INTER_LINEAR)
    top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
    left, right = int(round(dw - 0.1)), int(round(dw + 0.1))
    im = cv2.copyMakeBorder(im, top, bottom, left, right, cv2.BORDER_CONSTANT, value=color)  # add border
    return im, ratio, (dw, dh)



def convert_results(result_boxes, result_scores, result_classid):
    detect_objs = []
    for j in range(len(result_boxes)):
        box = result_boxes[j]
        x0, y0, x1, y1 = box
        conf = result_scores[j]
        # detect_objs.append({
        #     'xmin': int(x0),
        #     'ymin': int(y0),
        #     'xmax': int(x1),
        #     'ymax': int(y1),
        #     'confidence': float(conf),
        #     'name': categories[int(result_classid[j])]
        # })
        detect_objs.append({
            'x': int(x0),
            'y': int(y0),
            'width': int(x1-x0),
            'height': int(y1-y0),
            'confidence': float(conf),
            'name': categories[int(result_classid[j])]
        })

    target_objs = []
    for obj in detect_objs:
        if obj["name"] in target_categories:
            target_objs.append(obj)

    res = {
        "algorithm_data": {
            "is_alert": len(target_objs) > 0,
            "target_count": len(target_objs),
            "target_info": target_objs
        },
        "model_data": {
            "objects": detect_objs
        }
    }

    return json.dumps(res, indent=4)

if __name__ == "__main__":
    class time_count:
        def __init__(self):
            self.count = 0
            self.count1_call_times = 0
            self.names = []

        def init(self):
            self.count += 1
            self.count_call_times = 0

            if self.count == 1:
                pass
            elif self.count == 2:
                self.list = [[] for _ in range(self.count1_call_times)]
            elif self.count > 2:
                pass
            else:
                raise Exception("time_count")
            self.start = time.time()

        def __call__(self, name):
            self.end = time.time()
            if self.count == 1:
                self.count1_call_times += 1
                self.names.append(name)
            elif self.count > 1:
                self.list[self.count_call_times].append(self.end - self.start)
                self.count_call_times += 1
            else:
                raise Exception("time_count")
            self.start = time.time()

        def summury(self):
            print("==" * 20)
            spend_time_mean_overall = 0
            for idx in range(len(self.names)):
                name = self.names[idx]
                spend_time_list = self.list[idx]
                spend_time_mean = np.mean(spend_time_list) * 1000
                spend_time_std = np.std(spend_time_list) * 1000
                if spend_time_mean > 0.01:
                    print("{: <80}{: <20}{: <20}".format(name, round(spend_time_mean, 2), round(spend_time_std, 10)))
                spend_time_mean_overall += spend_time_mean
            print("{: <80}{: <20}".format("overall_time", round(spend_time_mean_overall, 1)))
            print("{: <80}{: <20}".format("overall_fps", round(1000 / spend_time_mean_overall, 1)))
            print("==" * 20)
else:
    class time_count:
        def __init__(self):
            pass

        def init(self):
            pass

        def __call__(self, name):
            pass

        def summury(self):
            pass
global tc
tc = time_count()

@torch.no_grad()
def init():

    global imgsz, stride, device, half

    # Load model
    device = torch.device(device)
    # model = DetectMultiBackend(model_path, device=device, dnn=False)
    model = attempt_load_weights(model_path, device=device)
    
    # stride = int(model.stride.max())
    # imgsz = check_img_size(imgsz, s=stride)  # check image size

    # Half
    model.half() if half else model.float()

    return model

@torch.no_grad()
def process_image(model, input_image, args=None, **kwargs):
    input_image = cv2.cvtColor(input_image, cv2.COLOR_BGR2RGB)    
    img = letterbox(input_image, imgsz, stride=stride, auto=True)[0]  # BGR
    tc('letterbox')
    img = img.transpose((2, 0, 1))[::-1]  # HWC to CHW, BGR to RGB
    img = np.expand_dims(img, axis=0)
    img = np.ascontiguousarray(img)
    img = torch.from_numpy(img).to(device)
    img = img.half() if half else img.float()  # uint8 to fp16/32
    img /= 255  # 0 - 255 to 0.0 - 1.0
    tc('255')
    pred = model(img, augment=False)[0]
    tc('infer')
    conf_thres = CONF_THRESH  # confidence threshold
    iou_thres = IOU_THRESHOLD  # NMS IOU threshold
    classes = None  # filter by class: --class 0, or --class 0 2 3
    agnostic_nms = False  # class-agnostic NMS
    max_det = 100  # maximum detections per image
    pred = ops.non_max_suppression(pred, conf_thres, iou_thres, max_det=max_det)
    tc('nms')
    det = pred[0]
    if len(det):
        det[:, :4] = ops.scale_boxes(img.shape[2:], det[:, :4], input_image.shape).round()
        result_boxes, result_scores, result_classid = det[:, :4], det[:, 4], det[:, 5]
    else:
        result_boxes, result_scores, result_classid = [], [], []
    tc('post')
    res = convert_results(result_boxes, result_scores, result_classid)
    tc('convert')
    return res

if __name__ == '__main__':
    model_path = '/project/train/models/exp/weights/best.pt'
    imgsz = 480
    # Test API

    img_paths = glob.glob("/home/data/*/*.jpg")
    model = init()

    total_time = 0
      
    for img_path in tqdm(img_paths):
        img = cv2.imread(img_path)
        start = time.time()
        tc.init()  
        result = process_image(model, img)
        print(result)
        end = time.time()
        total_time += end - start
    tc.summury()

    print(">> time >> " + str(total_time))
    print(">> fps >> " + str(len(img_paths) / total_time))