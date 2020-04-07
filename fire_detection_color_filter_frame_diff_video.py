import cv2
import os
import time
import datetime
from collections import deque
################################################################################

from tflearn.layers.core import *
from tflearn.layers.conv import *
from tflearn.layers.normalization import *
from tflearn.layers.estimator import regression


#################################################
def contrast_brightness_demo(image, c, b):  #其中c为对比度，b为每个像素加上的值（调节亮度）
    blank = np.zeros(image.shape, image.dtype)   #创建一张与原图像大小及通道数都相同的黑色图像
    dst = cv2.addWeighted(image, c, blank, 1-c, b) #c为加权值，b为每个像素所加的像素值
    ret, dst = cv2.threshold(dst, 25, 255, cv2.THRESH_BINARY)
    return dst


def frame_to_gray_using_color(frame): # codes from web, download for test

    B = frame[:, :, 0]
    G = frame[:, :, 1]
    R = frame[:, :, 2]
    val1 = G / (R + 1)
    val2 = B / (R + 1)
    val3 = B / (G + 1)
    R_mean = np.mean(R)
    # fireImg = np.array(np.where(R > R_mean, np.where(R >= G, np.where(G >= B, np.where(S >= 0.2, np.where(S >= (255 - R)*saturationTh/redThre, 255, 0), 0), 0), 0), 0))
    fireImg = np.array(np.where(R > R_mean, np.where(R >= G, np.where(G >= B, np.where(val1 >= 0.25,
                                                                                       np.where(val1 <= 0.65,
                                                                                                np.where(val2 >= 0.05,
                                                                                                         np.where(val2 <= 0.45,
                                                                                                                  np.where(val3 >= 0.2,
                                                                                                                           np.where(val3 <= 0.6, 255, 0), 0), 0),0), 0), 0), 0),0), 0))
    gray_fireImg = np.zeros([fireImg.shape[0], fireImg.shape[1], 1], np.uint8)
    gray_fireImg[:, :, 0] = fireImg
    gray_fireImg = cv2.GaussianBlur(gray_fireImg, (7, 7), 0)
    gray_fireImg = contrast_brightness_demo(gray_fireImg, 5.0, 25)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))

    gray_fireImg = cv2.morphologyEx(gray_fireImg, cv2.MORPH_CLOSE, kernel)
    # gray_fireImg = cv2.dilate(gray_fireImg, kernel)
    return gray_fireImg

def absdiff_demo(image_1, image_2, sThre):
    gray_image_1 = cv2.cvtColor(image_1, cv2.COLOR_BGR2GRAY)  # 灰度化
    gray_image_1 = cv2.GaussianBlur(gray_image_1, (3, 3), 0)  # 高斯滤波
    gray_image_2 = cv2.cvtColor(image_2, cv2.COLOR_BGR2GRAY)
    gray_image_2 = cv2.GaussianBlur(gray_image_2, (3, 3), 0)
    d_frame = cv2.absdiff(gray_image_1, gray_image_2)
    ret, d_frame = cv2.threshold(d_frame, sThre, 255, cv2.THRESH_BINARY)
    # result = scipy.ndimage.median_filter(d_frame, (5, 5))
    return d_frame


def construct_firenet(x, y, training=False):
    # Build network as per architecture in [Dunnings/Breckon, 2018]
    network = tflearn.input_data(shape=[None, y, x, 3], dtype=tf.float32)

    network = conv_2d(network, 64, 5, strides=4, activation='relu')

    network = max_pool_2d(network, 3, strides=2)
    network = local_response_normalization(network)

    network = conv_2d(network, 128, 4, activation='relu')

    network = max_pool_2d(network, 3, strides=2)
    network = local_response_normalization(network)

    network = conv_2d(network, 256, 1, activation='relu')

    network = max_pool_2d(network, 3, strides=2)
    network = local_response_normalization(network)

    network = fully_connected(network, 4096, activation='tanh')
    network = dropout(network, 0.5)

    network = fully_connected(network, 4096, activation='tanh')
    network = dropout(network, 0.5)

    network = fully_connected(network, 2, activation='softmax')

    # if training then add training hyperparameters
    if (training):
        network = regression(network, optimizer='momentum',
                             loss='categorical_crossentropy',
                             learning_rate=0.001)

    # constuct final model
    model = tflearn.DNN(network, checkpoint_path='firenet',
                        max_checkpoints=1, tensorboard_verbose=2)

    return model


def find_indexs(a, val):
    suffixs = []
    for i, value in enumerate(a):
        if value == val:
            suffixs.append(i)
    return suffixs


def extract_color_select_rect(frame, frame_2):
    
    frame_copy = frame_2.copy()    
    mask = frame_to_gray_using_color(frame)
    # cv2.namedWindow('Result of dilate2', 0)
    # cv2.imshow('Result of dilate2', mask)
    # cv2.waitKey(2)

    _, contours, hierarchy = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    candinates = []
    vertex = []
    centers = []
    property_contour = []

    cnt = 0
    for i in range(len(contours)):
        arclen = cv2.arcLength(contours[i], True)
        epsilon = max(3, int(arclen * 0.015))
        approx = cv2.approxPolyDP(contours[i], epsilon, False)
        area = cv2.contourArea(contours[i])
        rect = cv2.minAreaRect(contours[i])
        box = np.int0(cv2.boxPoints(rect))
        h = int(rect[1][0])
        w = int(rect[1][1])
        if min(h, w) == 0:
            ration = 0
        else:
            ration = max(h, w) / min(h, w)
        cv2.drawContours(frame_copy, [contours[i]], 0, (255, 255, 255), 2)

        # cv2.drawContours(frame_copy, contours, -1, (0, 255, 0), 2)
        if ration < 5 and area >= 20 and area < 3000 and approx.shape[0] > 3:
            # area_30_percent = 50176 * 0.3
            # area_enlage = area / area_30_percent
            cv2.polylines(frame_copy, [approx], True, (0, 0, 255), 2)
            shift_val = 10
            x_min = max(min(box[2][0], box[3][0], box[1][0], box[0][0]) - shift_val, 0)
            x_max = min(max(box[2][0], box[3][0], box[1][0], box[0][0]) + shift_val, frame_copy.shape[1])
            y_min = max(min(box[2][1], box[3][1], box[1][1], box[0][1]) - shift_val, 0)
            y_max = min(max(box[2][1], box[3][1], box[1][1], box[0][1]) + shift_val, frame_copy.shape[0])

            crop_pre = frame[y_min: y_max, x_min: x_max]
            crop = frame_2[y_min: y_max, x_min: x_max]

            # 对筛选出的区块利用帧差法查看是否在变化
            crop_diff = absdiff_demo(crop_pre, crop, 10)

            ref_pixel_sum = crop_diff.shape[0] * crop_diff.shape[1] * 255  # white picture

            # 对帧差法得到的结果进行判断，如果白色区域（值为255）占整副纯白图的10%以上，则认为该区域是在变化
            if crop_diff.sum() > ref_pixel_sum * 0.1:
                new_corners = np.array([[x_min, y_min], [x_max, y_min], [x_min, y_max], [x_max, y_max]])
                new_rect = cv2.minAreaRect(new_corners)
                new_box = np.int0(cv2.boxPoints(new_rect))
                candinates.append([crop, 1])
                vertex.append(new_box)
                centers.append(rect[0])
                fc = 0
                property_contour.append([area, approx.shape[0], fc])

            else:
                pass
                # cv2.namedWindow('Result of crop_diff', 0)
                # cv2.imshow('Result of crop_diff', crop_diff)
                # cv2.waitKey(2)
        cnt = cnt + 1

    cv2.namedWindow('Result of drawContours', 0)
    cv2.imshow('Result of drawContours', frame_copy)
    cv2.waitKey(2)

    return candinates, vertex, centers, property_contour


if __name__ == '__main__':

    ################################################################################
    # construct and display model
    model = construct_firenet(224, 224, training=False)
    print("Constructed FireNet ...")
    model.load(os.path.join("models/FireNet", "firenet"), weights_only=True)
    print("Loaded CNN network weights ...")

    ################################################################################
    # network input sizes
    rows = 224
    cols = 224
    # display and loop settings
    windowName = "Live Fire Detection - FireNet CNN"
    keepProcessing = True
    ################################################################################

    video = cv2.VideoCapture('161-fire_cut.mp4')
    print("Loaded video ...")
    # create window
    cv2.namedWindow(windowName, cv2.WINDOW_NORMAL)
    width = int(video.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(video.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = video.get(cv2.CAP_PROP_FPS)
    frame_time = round(100 / fps)
    fourcc = cv2.VideoWriter_fourcc('M', 'P', '4', '2')

    outVideo = cv2.VideoWriter('./fire_detection_video.avi', fourcc, fps, (width, height))

    # f = open('area_approx_fc.txt', '+w')
    # 记录上帧中出现火灾的位置信息，需要到下帧再次检测，防止颜色提区域的漏检
    candinates_fire_pre = []
    vertex_fire_pre = []
    centers_fire_pre = []
    property_contour_fire_pre = []

    ret, frame = video.read()
    frame_2_copy = frame
    cnt = 0
    # detect_ret_three_pre = [0,0,0]  # 前三帧的检测结果
    detect_ret_three_pre = deque(maxlen=2)
    nofire_cnt = 0
    while (keepProcessing):
        frame = frame_2_copy
        ret_2, frame_2 = video.read()

        if not ret_2:
            print("... end of video file reached")
            break

        candinates, vertex, centers, property_contour = extract_color_select_rect(frame, frame_2)
        # 将上帧中检测到的火灾位置区域放入本帧再次检测
        for i in range(len(candinates_fire_pre)):
            candinates.append(candinates_fire_pre[i])
            vertex.append(vertex_fire_pre[i])
            centers.append(centers_fire_pre[i])
            property_contour.append(property_contour_fire_pre[i])

        frame_2_copy = frame_2.copy()

        out_put_sets = []
        for i in range(len(candinates)):

            if candinates[i][0] is None:
                print("there is no candinates!")
            # cv2.imshow('candinates', candinates[i][0])
            # cv2.waitKey(2)
            small_frame = cv2.resize(candinates[i][0], (rows, cols), cv2.INTER_AREA)
            output = model.predict([small_frame])
            # if round(output[0][0]) == 1:
            #     cv2.imwrite('fire_blocks/fire_{}.jpg'.format(cnt), candinates[i][0])
            out_put_sets.append(round(output[0][0]))

        frame_current = frame_2.copy()
        width = int(frame_current.shape[1])
        height = int(frame_current.shape[0])

        time_stamp = datetime.datetime.now()
        date_now = time_stamp.strftime('%Y.%m.%d-%H:%M:%S')

        if 1 in out_put_sets:
            detect_ret_three_pre.append(1)
            suffixs = find_indexs(out_put_sets, 1)
            # 判断前两帧的检测结果是否至少有一帧为火灾
            if detect_ret_three_pre.count(1) >= 1:

                for k in range(len(suffixs)):

                    # 将上帧中检测到的火灾位置清空并放入新的火灾位置信息
                    candinates_fire_pre.clear()
                    vertex_fire_pre.clear()
                    centers_fire_pre.clear()
                    property_contour_fire_pre.clear()
                    candinates[suffixs[k]][1] = candinates[suffixs[k]][1] + 1
                    if candinates[suffixs[k]][1] <= 2:
                        candinates_fire_pre.append(candinates[suffixs[k]])
                        vertex_fire_pre.append(vertex[suffixs[k]])
                        centers_fire_pre.append(centers[suffixs[k]])
                        property_contour_fire_pre.append(property_contour[suffixs[k]])

                    cv2.drawContours(frame_current, [vertex[suffixs[k]]], 0, (0, 0, 255), 2)
                    print("this is {}th frame:".format(cnt))
                    print("area:{},approx.shape[0]:{},fc:{}".format(property_contour[suffixs[k]][0],
                                                                    property_contour[suffixs[k]][1],
                                                                    property_contour[suffixs[k]][2]))
                    print("--------end------------")
                # detect_ret_three_pre.append(1)
                cv2.rectangle(frame_current, (0, 0), (width, height), (0, 0, 255), 50)
                cv2.putText(frame_current, 'FIRE', (int(width / 20), int(height / 8)),
                            cv2.FONT_HERSHEY_SIMPLEX, 4, (255, 255, 255), 10, cv2.LINE_AA)
                # cv2.putText(frame_current, str("detection frame {}".format(cnt)), (int(width / 20), int(height / 4)),
                #             cv2.FONT_HERSHEY_SIMPLEX, 2, (255, 255, 255), 6, cv2.LINE_AA)
                cv2.putText(frame_current, date_now, (int(width / 20), int(height / 4)),
                            cv2.FONT_HERSHEY_SIMPLEX, 4, (255, 255, 255), 10, cv2.LINE_AA)

            else:
                nofire_cnt = nofire_cnt + 1
                # detect_ret_three_pre.append(0)
                cv2.rectangle(frame_current, (0, 0), (width, height), (0, 255, 0), 50)
                cv2.putText(frame_current, 'NO FIRE', (int(width / 20), int(height / 8)),
                            cv2.FONT_HERSHEY_SIMPLEX, 4, (255, 255, 255), 10, cv2.LINE_AA)
                # cv2.putText(frame_current, str("detection frame {}".format(cnt)), (int(width / 20), int(height / 4)),
                #             cv2.FONT_HERSHEY_SIMPLEX, 2, (255, 255, 255), 6, cv2.LINE_AA)
                cv2.putText(frame_current, date_now, (int(width / 20), int(height / 4)),
                            cv2.FONT_HERSHEY_SIMPLEX, 4, (255, 255, 255), 10, cv2.LINE_AA)
        else:
            nofire_cnt = nofire_cnt + 1
            detect_ret_three_pre.append(0)
            cv2.rectangle(frame_current, (0, 0), (width, height), (0, 255, 0), 50)
            cv2.putText(frame_current, 'NO FIRE', (int(width / 20), int(height / 8)),
                        cv2.FONT_HERSHEY_SIMPLEX, 4, (255, 255, 255), 10, cv2.LINE_AA)
            # cv2.putText(frame_current, str("detection frame {}".format(cnt)), (int(width / 20), int(height / 4)),
            #             cv2.FONT_HERSHEY_SIMPLEX, 2, (255, 255, 255), 6, cv2.LINE_AA)
            cv2.putText(frame_current, date_now, (int(width / 20), int(height / 4)),
                        cv2.FONT_HERSHEY_SIMPLEX, 4, (255, 255, 255), 10, cv2.LINE_AA)


            # if cnt > 3:
            #     detect_ret_three_pre.pop()
            #     detect_ret_three_pre.append(0)
        print("nofire_cnt",nofire_cnt)
        outVideo.write(frame_current)
        cv2.imshow(windowName, frame_current)
        cv2.waitKey(1)
        cnt = cnt + 1
        # if cnt == 442:
        #     break
        time.sleep(0.05)





