'''
- SBD: 10 hàng x 6 cột
- Mã đề: 10 hàng x 3 cột
'''
import cv2, os, shutil, numpy as np
from pathlib import Path
from ultralytics import YOLO

BASE_DIR = Path(__file__).resolve().parent.parent
REGION_MODEL = BASE_DIR / "AI/best/regions/best.pt"
BUBBLE_MODEL = BASE_DIR / "AI/best/bubbles/best.pt"

REGION_CLASSES = {0: "Answer_region", 1: "MaDe_region", 2: "SBD_region"}
BUBBLE_CLASSES = {0: "Filled", 1: "Unfilled"}

REGION_COLOR = {"Answer_region": (255, 0, 0), "MaDe_region": (255, 255, 0), "SBD_region": (128, 0, 128)}
BUBBLE_COLOR = {"Filled": (0, 255, 0), "Unfilled": (0, 0, 255)}

OUT_DIR   = "out"
MAX_COLS_ANSWER = 4

region_model = YOLO(REGION_MODEL)
bubble_model = YOLO(BUBBLE_MODEL)

# def clear_output_dir(path="out"):
#     if os.path.exists(path):
#         shutil.rmtree(path, ignore_errors=True)
#     os.makedirs(path, exist_ok=True)

def rotate_by_90(img, k):
    k = k % 4
    if k == 0:
        return img
    elif k == 1:
        return cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
    elif k == 2:
        return cv2.rotate(img, cv2.ROTATE_180)
    else:
        return cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
    
def detect_bubbles(img, conf=0.5):
    res = bubble_model(img, conf=conf, verbose=False)[0]
    arr = []
    for box, cls in zip(res.boxes.xyxy, res.boxes.cls):
        x1, y1, x2, y2 = map(int, box.tolist())
        arr.append({
            "box": (x1, y1, x2, y2),
            "center": ((x1 + x2) // 2, (y1 + y2) // 2),
            "class": BUBBLE_CLASSES.get(int(cls))
        })
    return arr

def filter_normal_bubbles(bubbles, scale_low=0.5, scale_high=1.5):
    # Dùng để loại ô đen to khác thường
    if not bubbles:
        return []
    areas = [(b["box"][2] - b["box"][0]) * (b["box"][3] - b["box"][1]) for b in bubbles]
    med = np.median(areas)
    good = []
    for b in bubbles:
        area = (b["box"][2] - b["box"][0]) * (b["box"][3] - b["box"][1])
        if med * scale_low <= area <= med * scale_high:
            good.append(b)
            
    return good

def get_bubble_rect(bubble):
    x1 = bubble["box"][0]
    y1 = bubble["box"][1]
    x2 = bubble["box"][2]
    y2 = bubble["box"][3]
    return x1, y1, x2, y2

def read_sbd(crop):
    """
    Đọc vùng SBD dạng lưới 10x6 từ ảnh `crop`.
    Trả về chuỗi các số tìm được, hoặc None nếu không hợp lệ.
    """
    # Detect bubble lần 1
    bubbles = detect_bubbles(crop, conf=0.5)

    # Nếu detect ít hơn 5 bubble thì nới conf ra
    if len(bubbles) < 5:
        bubbles = detect_bubbles(crop, conf=0.35)

    # Không detect được gì
    if not bubbles:
        return None

    # Lọc bubble [bình thường]
    bubbles = filter_normal_bubbles(bubbles)
    if not bubbles:
        return None

    # vẽ bounding box
    min_x, min_y, max_x, max_y = get_bubble_rect(bubbles[0])
    for b in bubbles:
        x1, y1, x2, y2 = get_bubble_rect(b)
        min_x = min(min_x, x1)
        min_y = min(min_y, y1)
        max_x = max(max_x, x2)
        max_y = max(max_y, y2)        
        cv2.rectangle(crop, (x1, y1), (x2, y2), BUBBLE_COLOR.get(b["class"]), 1)
    box_w = max_x - min_x
    box_h = max_y - min_y
    box_w = box_w // 6
    box_h = box_h // 10

    areas = [(b["box"][2] - b["box"][0]) * (b["box"][3] - b["box"][1]) for b in bubbles]
    med = np.median(areas)
    if not(med * 0.2 < box_w * box_h < med * 1.8):
        print(med, box_w * box_h)
        return None

    mat = [[False for j in range(6)] for i in range(10)]
    for b in bubbles:
        if b["class"] == BUBBLE_CLASSES.get(0):
            xc, yc = b["center"]
            j = (xc - min_x) // box_w
            i = (yc - min_y) // box_h
            mat[i][j] = True

    result = ["?"] * 6
    for i in range(10):
        for j in range(6):
            if mat[i][j]:
                result[j] = str(i)
            #     cv2.rectangle(crop, (min_x + j * box_w, min_y + i * box_h), (min_x + (j + 1) * box_w, min_y + (i + 1) * box_h), (0, 127, 255), 2)
            # else: 
            #     cv2.rectangle(crop, (min_x + j * box_w, min_y + i * box_h), (min_x + (j + 1) * box_w, min_y + (i + 1) * box_h), (127, 127, 0), 1)
    # cv2.imwrite(os.path.join(angle_dir, "SBD.jpg"), crop)
    return "".join(result)

def read_made(crop):
    """
    Đọc vùng MaDe dạng lưới 10x3 từ ảnh `crop`.
    Trả về chuỗi các số tìm được, hoặc None nếu không hợp lệ.
    """
    # Detect bubble lần 1
    bubbles = detect_bubbles(crop, conf=0.5)

    # Nếu detect ít hơn 5 bubble thì nới conf ra
    if len(bubbles) < 5:
        bubbles = detect_bubbles(crop, conf=0.35)

    # Không detect được gì
    if not bubbles:
        return None

    # Lọc bubble [bình thường]
    bubbles = filter_normal_bubbles(bubbles)
    if not bubbles:
        return None

    # vẽ bounding box
    min_x, min_y, max_x, max_y = get_bubble_rect(bubbles[0])
    for b in bubbles:
        x1, y1, x2, y2 = get_bubble_rect(b)
        min_x = min(min_x, x1)
        min_y = min(min_y, y1)
        max_x = max(max_x, x2)
        max_y = max(max_y, y2)        
        cv2.rectangle(crop, (x1, y1), (x2, y2), BUBBLE_COLOR.get(b["class"]), 1)
    box_w = max_x - min_x
    box_h = max_y - min_y
    box_w = box_w // 3
    box_h = box_h // 10

    areas = [(b["box"][2] - b["box"][0]) * (b["box"][3] - b["box"][1]) for b in bubbles]
    med = np.median(areas)
    if not(med * 0.2 < box_w * box_h < med * 1.8):
        return None

    mat = [[False for j in range(3)] for i in range(10)]
    for b in bubbles:
        if b["class"] == BUBBLE_CLASSES.get(0):
            xc, yc = b["center"]
            j = (xc - min_x) // box_w
            i = (yc - min_y) // box_h
            mat[i][j] = True

    result = ["?"] * 3
    for i in range(10):
        for j in range(3):
            if mat[i][j]:
                result[j] = str(i)
            #     cv2.rectangle(crop, (min_x + j * box_w, min_y + i * box_h), (min_x + (j + 1) * box_w, min_y + (i + 1) * box_h), (0, 127, 255), 2)
            # else: 
            #     cv2.rectangle(crop, (min_x + j * box_w, min_y + i * box_h), (min_x + (j + 1) * box_w, min_y + (i + 1) * box_h), (127, 127, 0), 1)
    # cv2.imwrite(os.path.join(angle_dir, "MADE.jpg"), crop)
    return "".join(result)

def read_answer(answers_region):
    n_section = 1
    groups = {}
    group_i = 0
    for region in answers_region:
        crop = region["crop"].copy()
        # Detect bubble lần 1
        bubbles = detect_bubbles(crop, conf=0.5)

        # Nếu detect ít hơn 5 bubble thì nới conf ra
        if len(bubbles) < 5:
            bubbles = detect_bubbles(crop, conf=0.35)

        # Không detect được gì
        if not bubbles:
            return None

        # Lọc bubble [bình thường]
        bubbles = filter_normal_bubbles(bubbles)
        if not bubbles:
            return None

        # vẽ bounding box
        for b in bubbles:
            x1, y1, x2, y2 = get_bubble_rect(b)
            cv2.rectangle(crop, (x1, y1), (x2, y2), BUBBLE_COLOR.get(b["class"]), 1)

        widths = [(b["box"][2] - b["box"][0]) for b in bubbles]
        med_w = np.median(widths)

        bubbles = sorted(bubbles, key=lambda e: e["box"][0])

        curr_b = bubbles[0]
        for b in bubbles:
            if abs(curr_b["box"][0] - b["box"][0]) > med_w * 2:
                group_i += 1
            groups.setdefault(group_i, []).append(b)
            curr_b = b

        # cv2.imwrite(os.path.join(angle_dir, f"DAPAN_{n_section}.jpg"), crop)
        n_section += 1
        group_i += 1
    # print("Number of group: ", len(groups))
    result = ["?"] * len(groups) * 10 # Mỗi group có 10 câu
    for b_i, bubbles in groups.items():
        min_x, min_y, max_x, max_y = get_bubble_rect(bubbles[0])
        for b in bubbles:
            x1, y1, x2, y2 = get_bubble_rect(b)
            min_x = min(min_x, x1)
            min_y = min(min_y, y1)
            max_x = max(max_x, x2)
            max_y = max(max_y, y2)    

        box_w = max_x - min_x
        box_h = max_y - min_y
        box_w = box_w // 4
        box_h = box_h // 10

        areas = [(b["box"][2] - b["box"][0]) * (b["box"][3] - b["box"][1]) for b in bubbles]
        med = np.median(areas)
        if not(med * 0.2 < box_w * box_h < med * 1.8):
            return None

        mat = [[False for j in range(4)] for i in range(10)]
        for b in bubbles:
            if b["class"] == BUBBLE_CLASSES.get(0):
                xc, yc = b["center"]
                j = (xc - min_x) // box_w
                i = (yc - min_y) // box_h
                mat[i][j] = True

        for i in range(10):
            for j in range(4):
                if mat[i][j]:
                    result[b_i * 10 + i] = str(j)
    return result

def is_region_correct(sbd_region, made_region, answer_region):
    if len(sbd_region) != 1:
        print("Số lượng khu vực SBD không phải là 1")
        return False

    if len(made_region) != 1:
        print("Số lượng khu vực Ma De không phải là 1")
        return False

    if len(answer_region) == 0:
        print("Số lượng khu vực Dap An là 0")
        return False

    def get_priority(region):
        first_box = sorted(region, key=lambda e: e["box"][0] + e["box"][1])[0]
        return first_box["box"][0] + first_box["box"][1]

    if not(get_priority(sbd_region) < get_priority(made_region) < get_priority(answer_region)):
        print("Thứ tự các vùng không hợp lệ")
        return False

    if abs(sbd_region[0]["box"][1] - made_region[0]["box"][1]) > abs(sbd_region[0]["box"][0] - made_region[0]["box"][0]):
        print("Thứ tự các vùng không hợp lệ")
        return False
    
    return True

class No_Le_AI:
    def __init__(self):
        pass

    def process(self, image_path):
        # clear_output_dir(OUT_DIR)

        img0 = cv2.imread(image_path)
        if img0 is None:
            raise FileNotFoundError(f"Không tìm thấy ảnh: {image_path}")
        
        angle_infos = []
        best_info = None
        for k in range(4):
            angle = (k * 90) % 360
            # print("angle: ", angle)
            img_rot = rotate_by_90(img0, k)

            angle_dir = os.path.join(OUT_DIR, f"angle_{angle:03d}")
            # os.makedirs(angle_dir, exist_ok=True)
            # cv2.imwrite(os.path.join(angle_dir, "full.jpg"), img_rot)

            det = region_model(img_rot, verbose=False)[0]
            regions = {}
            for box, cls in zip(det.boxes.xyxy, det.boxes.cls):
                x1, y1, x2, y2 = map(int, box.tolist())
                name = REGION_CLASSES.get(int(cls))
                crop = img_rot[y1:y2, x1:x2]
                regions.setdefault(name, []).append({"crop": crop, "box": (x1, y1, x2, y2)})
            
            sbd_region  = regions.get("SBD_region", [])
            made_region = regions.get("MaDe_region", [])
            answers_region = regions.get("Answer_region", [])

            if not is_region_correct(sbd_region, made_region, answers_region):
                continue
            
            sbd  = read_sbd(sbd_region[0]["crop"].copy())
            # if sbd:
            #     print("Số báo danh: ", sbd)

            made  = read_made(made_region[0]["crop"].copy())
            # if made:
            #     print("Mã đề: ", made)

            answers_region = sorted(answers_region, key=lambda e: e["box"][1])
            answers  = read_answer(answers_region)
            answers_dict = {}
            if answers:
                answers_dict = {
                    str(i + 1): ("?" if ans == "?" else chr(ord("A") + int(ans)))
                    for i, ans in enumerate(answers)
                }
            else:
                answers_dict = None
            result_json = {
                "sbd": sbd,
                "made": made,
                "answers": answers_dict,
            }
            
            return result_json
