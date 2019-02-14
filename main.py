import numpy as np
import keras
from keras.models import Sequential
from keras.layers import Dense, Dropout, Flatten
from keras.layers import Conv2D, MaxPooling2D
from keras.optimizers import Adam
from keras.models import load_model
from tensorflow.python.client import device_lib
from keras import backend as K
import tensorflow as tf
import cv2


# This method draws the optical flow onto img with a given step (distance between one arrow origin and the other)
def draw_flow(img, flow, step=16):
    h, w = img.shape[:2]
    y, x = np.mgrid[step/2:h:step, step/2:w:step].reshape(2,-1).astype(int)
    fx, fy = flow[y,x].T
    lines = np.vstack([x, y, x+fx, y+fy]).T.reshape(-1, 2, 2)
    lines = np.int32(lines + 0.5)
    vis = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    cv2.polylines(vis, lines, 0, (0, 255, 0))
    for (x1, y1), (x2, y2) in lines:
        cv2.circle(vis, (x1, y1), 1, (0, 255, 0), -1)
    return vis

# This method cuts top and bottom portions of the frame (which are only black areas of the car's dashboard or sky)
def cutTopAndBottom(img):
    height, width, channels = img.shape
    heightBeginning = 20
    heightEnd = height - 30
    crop_img = img[heightBeginning : heightEnd, 0 : width]
    return crop_img

def setupNvidiaModel(inputShape):
    model = Sequential()

    # Normalization layer
    normLayer = keras.layers.BatchNormalization()
    model.add(normLayer)

    # Convolution Layer 1
    convLayer = Conv2D(filters=12,
                       kernel_size=(5, 5),
                       strides=(1, 1),
                       activation='relu',
                       input_shape=inputShape)
    model.add(convLayer)
    # Pooling Layer 1
    poolingLayer = MaxPooling2D(pool_size=(2, 2),
                                strides=(2, 2))
    model.add(poolingLayer)

    # Convolution Layer 2
    convLayer = Conv2D(filters=24,
                       kernel_size=(5, 5),
                       activation='relu')
    model.add(convLayer)
    # Pooling Layer 2
    poolingLayer = MaxPooling2D(pool_size=(2, 2),
                                strides=(2, 2))
    model.add(poolingLayer)

    # Convolution Layer 3
    convLayer = Conv2D(filters=36,
                       kernel_size=(3, 3),
                       activation='relu')
    model.add(convLayer)
    # Pooling Layer 3
    poolingLayer = MaxPooling2D(pool_size=(2, 2),
                                strides=(2, 2))
    model.add(poolingLayer)

    # Convolution Layer 4
    convLayer = Conv2D(filters=48,
                       kernel_size=(3, 3),
                       activation='relu')
    model.add(convLayer)
    # Pooling Layer 4
    poolingLayer = MaxPooling2D(pool_size=(2, 2),
                                strides=(2, 2))
    model.add(poolingLayer)

    # Flatten
    model.add(Flatten())

    # Dense layer 1
    denseLayer = Dense(1164,
                       activation='relu')
    model.add(denseLayer)
    # Dense layer 2
    denseLayer = Dense(100,
                       activation='relu')
    model.add(denseLayer)
    # Dense layer 3
    denseLayer = Dense(50,
                       activation='relu')
    model.add(denseLayer)
    # Dense layer 4
    denseLayer = Dense(10,
                       activation='relu')
    model.add(denseLayer)
    # Dense layer 5
    denseLayer = Dense(1)
    model.add(denseLayer)

    # Compilation
    model.compile(Adam(lr=0.001),
                  loss="mse",
                  metrics=["mse"])

    return model


def setupTestModel(inputShape):
    model = Sequential()
    # Adding the first convolutional layer
    convLayer = Conv2D(filters=16,
                       kernel_size=(5, 5),
                       strides=(1, 1),
                       activation='relu',
                       input_shape=inputShape)
    model.add(convLayer)
    # First pooling
    poolingLayer = MaxPooling2D(pool_size=(2, 2),
                                strides=(2, 2))
    model.add(poolingLayer)
    # Adding the second convolutional layer
    convLayer = Conv2D(filters=32,
                       kernel_size=(5, 5),
                       activation='relu')
    model.add(convLayer)
    # Adding the second pooling layer
    poolingLayer = MaxPooling2D(pool_size=(2, 2))
    model.add(poolingLayer)
    # Flatten
    model.add(Flatten())
    # Dense layer 1
    denseLayer = Dense(100,
                       activation='relu')
    model.add(denseLayer)
    # Dense layer 2
    denseLayer = Dense(1)
    model.add(denseLayer)

    # Compilation
    model.compile(Adam(lr=0.001),
                  loss="mse",
                  metrics = ["mse"])

    return model


############ IMPORTANT VARIABLES ###########
batchSize = 200
############################################


# Reading all the speed ground truths
print("Reading speed ground truths")
file = open("./sourceData/train.txt")
speedTruthArrayString = file.readlines()
speedTruthArray = []
for numeric_string in speedTruthArrayString:
    numeric_string = numeric_string.strip('\n')
    speedTruthArray.append(float(numeric_string))
file.close()
print("Read " + str(len(speedTruthArray)) + " values")

# Uncomment to check if GPU is correcetly detected
# print(device_lib.list_local_devices())
# print(K.tensorflow_backend._get_available_gpus())

# GPU settings to allow memory growth
# config = tf.ConfigProto()
# config.gpu_options.allow_growth = True
# config.log_device_placement=True
# sess = tf.Session(config=config)  #With the two options defined above


# Opening training video
videoFeed = cv2.VideoCapture('./sourceData/train.mp4')
videoLengthInFrames = int(videoFeed.get(cv2.CAP_PROP_FRAME_COUNT))

# Reading the first frame
coupleCounter = 0
frameCoupleArray = []
ret1, oldFrame = videoFeed.read()
oldFrameGrey = cv2.cvtColor(oldFrame, cv2.COLOR_BGR2GRAY)

# Saving the size of the flow
oldFrameGrey = cutTopAndBottom(oldFrameGrey)
oldFrameGrey = cv2.equalizeHist(oldFrameGrey)
dummyFlow = cv2.calcOpticalFlowFarneback(oldFrameGrey , oldFrameGrey, 0.5, 0.5, 5, 20, 3, 5, 1.2, 0)
flowShape = dummyFlow.shape  # Original non cropped size is (480, 640, 2)

# Setting up the CNN model
model = setupNvidiaModel(flowShape)

# Iterating through all couples of frames of the video
frameCounter = 0
batchFrames = []
batchSpeeds = []
while(videoFeed.isOpened()):

    # Read a couple of new frames from the video feed
    ret2, newFrame = videoFeed.read()

    # Convert to greyscale
    newFrameGrey = cv2.cvtColor(newFrame, cv2.COLOR_BGR2GRAY)

    # Cut top and bottom portions of the image
    newFrameGrey = cutTopAndBottom(newFrameGrey)

    # Apply Histogram Equalization to increase contrast
    newFrameGrey = cv2.equalizeHist(newFrameGrey)

    # Calculate flow for this couple
    flow = cv2.calcOpticalFlowFarneback(oldFrameGrey , newFrameGrey, 0.5, 0.5, 5, 20, 3, 5, 1.2, 0)

    # Saving the couple of data and label
    batchFrames.append(flow)
    batchSpeeds.append(speedTruthArray[coupleCounter])

    # Incrementing couples counter and swapping frames
    coupleCounter = coupleCounter + 1
    oldFrameGrey = newFrameGrey
    print(str(coupleCounter))
    cv2.imshow('frame',draw_flow(newFrameGrey, flow))
    cv2.waitKey(1)

    # Training batch
    frameCounter = frameCounter + 1
    if frameCounter == batchSize or (coupleCounter+1) == videoLengthInFrames:
        # Preparing data
        X = np.array(batchFrames)
        Y = np.array(batchSpeeds)
        #with tf.device('/cpu:0'):   #Uncomment to use CPU instead of GPU
        model.fit(x=X,
                  y=Y,
                  verbose=1,
                  epochs=5,
                  batch_size=20
                  )
        # Resetting counter and x and y arrays
        frameCounter = 0
        batchFrames = []
        batchSpeeds = []


# Saving the trained model
model.save('speed_model.h5')  # creates a HDF5 file 'speed_model.h5'
#model = load_model('speed_model.h5')

videoFeed.release()
cv2.destroyAllWindows()




