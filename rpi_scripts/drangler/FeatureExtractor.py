import numpy as np
from scipy.stats import iqr


def extract(frame_collection):
    data_collection = []
    for frame in frame_collection:
        data = []
        for signal in frame:
            data = np.append(data, get_features(signal))

        data_collection.append(np.array(data))
    return np.array(data_collection)


def get_features_from_frame(frame):
    data = []
    for i in range(0, frame.shape[1]):
        data = np.append(data, get_features(frame[:, i]))
    return data


def get_features(signal):
    return [
        np.mean(signal),             # mean
        np.var(signal),              # var
        np.median(signal),           # median
        iqr(signal),                 # iqr
        np.std(signal),              # std
        np.max(signal),              # max
        np.min(signal),              # min
        mad(signal)                  # mad
    ]


# Time domain
def mean(signal):
    return np.mean(signal)


def median(signal):
    return np.median(signal)


def variance(signal):
    return np.var(signal)


def mad(data):
    return np.mean(np.absolute(data - np.mean(data)))
