"""
"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import tensorflow as tf
import numpy as np


class Norm(object):
    """singletance pattern
    """
    __instance = None

    def __new__(clz, real_data=None):
        if not Norm.__instance:
            Norm.__instance = object.__new__(clz)
        else:
            print("Instance Exists! :D")
        return Norm.__instance

    def __init__(self, real_data=None):
        """
        params
        ------
        real_data : float, shape=[#, length=100, players=11, features=4]

        note
        ----
        feature :
            x, y, z, and player position
        """
        if real_data is not None:
            self.__real_data = real_data
            self.__basket_left = [4, 25]
            self.__basket_right = [90, 25]
            self.__norm_dict = {}
            # position normalization
            self.__normalize_pos()

    def get_normed_data(self):
        return np.concatenate(
            [
                # ball
                self.__real_data[:, :, 0, :3].reshape(
                    [self.__real_data.shape[0], self.__real_data.shape[1], 1 * 3]),
                # players
                self.__real_data[:, :, 1:, :2].reshape(
                    [self.__real_data.shape[0], self.__real_data.shape[1], 10 * 2])
            ], axis=-1
        )

    def recover_data(self, norm_data):
        # X
        norm_data[:, :, [0, 3, 5, 7, 9, 11, 13, 15, 17, 19, 21]] = norm_data[:, :, [
            0, 3, 5, 7, 9, 11, 13, 15, 17, 19, 21]] * self.__norm_dict['x']['stddev'] + self.__norm_dict['x']['mean']
        # Y
        norm_data[:, :, [1, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22]] = norm_data[:, :, [
            1, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22]] * self.__norm_dict['y']['stddev'] + self.__norm_dict['y']['mean']
        # Z
        norm_data[:, :, 2] = norm_data[:, :, 2] * \
            self.__norm_dict['z']['stddev'] + self.__norm_dict['z']['mean']
        return norm_data

    def __normalize_pos(self):
        """ directly normalize player x,y,z on self.__real_data
        """
        axis_list = ['x', 'y', 'z']
        for i, axis_ in enumerate(axis_list):
            if axis_ == 'z':  # z
                mean_ = np.mean(
                    self.__real_data[:, :, 0, i])
                stddev_ = np.std(
                    self.__real_data[:, :, 0, i])
                self.__real_data[:, :, 0, i] = (
                    self.__real_data[:, :, 0, i] - mean_) / stddev_
                self.__norm_dict[axis_] = {}
                self.__norm_dict[axis_]['mean'] = mean_
                self.__norm_dict[axis_]['stddev'] = stddev_
            else:  # x and y
                mean_ = np.mean(
                    self.__real_data[:, :, :, i])
                stddev_ = np.std(
                    self.__real_data[:, :, :, i])
                self.__real_data[:, :, :, i] = (
                    self.__real_data[:, :, :, i] - mean_) / stddev_
                self.__basket_left[i] = (
                    self.__basket_left[i] - mean_) / stddev_
                self.__basket_right[i] = (
                    self.__basket_right[i] - mean_) / stddev_
                self.__norm_dict[axis_] = {}
                self.__norm_dict[axis_]['mean'] = mean_
                self.__norm_dict[axis_]['stddev'] = stddev_


def testing_real():
    real_data = np.load("../data/FEATURES.npy")
    print('real_data.shape', real_data.shape)
    normer = Norm(real_data)
    real_data = normer.get_normed_data()
    print('real_data.shape', real_data.shape)


def testing():
    dummy = np.ones(shape=[512, 100, 11, 4])
    normer = Norm(dummy)
    dummy_samples = tf.ones(shape=[512, 100, 23 + 70])
    normer.extract_features(dummy_samples)


if __name__ == '__main__':
    testing_real()
