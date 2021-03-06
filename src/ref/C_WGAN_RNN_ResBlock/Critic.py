"""
modeling
"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os
import time
import shutil
import numpy as np
import tensorflow as tf
from tensorflow.contrib import rnn
from tensorflow.contrib import layers
from utils import DataFactory
import Libs as libs


class C_MODEL(object):
    """ 
    """

    def __init__(self, config, graph):
        """ TO build up the graph
        Inputs
        ------
        config : 
            * batch_size : mini batch size
            * log_dir : path to save training summary
            * learning_rate : adam's learning rate
            * hidden_size : number of hidden units in LSTM
            * rnn_layers : number of stacked LSTM 
            * seq_length : length of LSTM
            * latent_dims : dimensions of latent feature
            * penalty_lambda = gradient penalty's weight, ref from  paper of 'improved-wgan'
        graph : 
            tensorflow default graph
        """
        self.data_factory = DataFactory()
        # hyper-parameters
        self.batch_size = config.batch_size
        self.log_dir = config.log_dir
        self.learning_rate = config.learning_rate
        self.hidden_size = config.hidden_size
        self.rnn_layers = config.rnn_layers
        self.seq_length = config.seq_length
        self.latent_dims = config.latent_dims
        self.penalty_lambda = config.penalty_lambda
        self.if_log_histogram = config.if_log_histogram
        self.n_resblock = config.n_resblock
        # steps
        self.__global_steps = tf.train.get_or_create_global_step(graph=graph)
        self.__steps = 0
        # data
        self.__G_samples = tf.placeholder(dtype=tf.float32, shape=[
            self.batch_size, self.seq_length, 10], name='G_samples')
        self.__X = tf.placeholder(dtype=tf.float32, shape=[
            self.batch_size, self.seq_length, 10], name='real_data')
        # TODO mismatched conditional constraints
        # self.__mismatched_cond = tf.placeholder(dtype=tf.float32, shape=[
        #     self.batch_size, self.seq_length, self.num_features], name='mismatched_cond)
        self.__matched_cond = tf.placeholder(dtype=tf.float32, shape=[
            self.batch_size, self.seq_length, 13], name='matched_cond')
        # adversarial learning : wgan
        self.__build_wgan()

        # summary
        self.__summary_op = tf.summary.merge(tf.get_collection('C'))
        self.__summary_valid_op = tf.summary.merge(
            tf.get_collection('C_valid'))
        self.summary_writer = tf.summary.FileWriter(
            self.log_dir + 'C')
        self.valid_summary_writer = tf.summary.FileWriter(
            self.log_dir + 'C_valid')

    def __build_wgan(self):
        with tf.name_scope('WGAN'):
            # inference
            real_scores = self.inference(self.__X, self.__matched_cond)
            fake_scores = self.inference(
                self.__G_samples, self.__matched_cond, reuse=True)
            # loss function
            self.__loss, F_real, F_fake, grad_pen = self.__loss_fn(
                self.__X, self.__G_samples, fake_scores, real_scores, self.penalty_lambda)
            theta = self.__get_var_list()
            with tf.name_scope('C_optimizer') as scope:
                C_optimizer = tf.train.AdamOptimizer(
                    learning_rate=self.learning_rate, beta1=0.5, beta2=0.9)
                grads = tf.gradients(self.__loss, theta)
                grads = list(zip(grads, theta))
                self.__train_op = C_optimizer.apply_gradients(
                    grads_and_vars=grads, global_step=self.__global_steps)
            # logging
            for grad, var in grads:
                self.__summarize(var.name, grad, collections='C',
                                 postfix='gradient')
            tf.summary.scalar('C_loss', self.__loss,
                              collections=['C', 'C_valid'])
            tf.summary.scalar('F_real', F_real, collections=['C'])
            tf.summary.scalar('F_fake', F_fake, collections=['C'])
            tf.summary.scalar('grad_pen', grad_pen, collections=['C'])

    def __summarize(self, name, value, collections, postfix=''):
        """ Helper to create summaries for activations.
        Creates a summary that provides a histogram of activations.
        Creates a summary that measures the sparsity of activations.
        Args
        ----
        name : string
        value : Tensor
        collections : list of string
        postfix : string
        Returns
        -------
            nothing
        """
        if self.if_log_histogram:
            tensor_name = name + '/' + postfix
            tf.summary.histogram(tensor_name,
                                 value, collections=collections)
            # tf.summary.scalar(tensor_name + '/sparsity',
            #                   tf.nn.zero_fraction(x), collections=collections)

    def __get_var_list(self):
        """ to get both Generator's and Discriminator's trainable variables
        and add trainable variables into histogram
        """
        trainable_V = tf.trainable_variables()
        theta = []
        for _, v in enumerate(trainable_V):
            if v.name.startswith('C'):
                theta.append(v)
                self.__summarize(v.op.name, v, collections='C',
                                 postfix='Trainable')
        return theta

    def __leaky_relu(self, features, alpha=0.2):
        return tf.maximum(features, alpha * features)

    def inference(self, inputs, conds, reuse=False):
        """
        Inputs
        ------
        inputs : float, shape=[batch_size, seq_length=100, features=10]
            real(from data) or fake(from G)
        conds : float, shape=[batch_size, swq_length=100, features=13]

        Return
        ------
        score : float
            real(from data) or fake(from G)
        """
        with tf.variable_scope('C', reuse=reuse):
            concat_ = tf.concat([conds, inputs], axis=-1)
            # # extract hand-crafted feature
            # concat_input = self.data_factory.extract_features(concat_input)

            with tf.variable_scope('conv_input') as scope:
                conv_input = tf.layers.conv1d(
                    inputs=concat_,
                    filters=256,
                    kernel_size=5,
                    strides=1,
                    padding='same',
                    activation=libs.leaky_relu,
                    kernel_initializer=layers.xavier_initializer(),
                    bias_initializer=tf.zeros_initializer(),
                    reuse=scope.reuse,
                    name=scope.name
                )
                print(conv_input)
            # residual block
            next_input = conv_input
            for i in range(self.n_resblock):
                res_block = libs.residual_block('Res' + str(i), next_input)
                next_input = res_block
                print(next_input)
            with tf.variable_scope('linear_result') as scope:
                flatten_ = layers.flatten(next_input)
                linear_result = layers.fully_connected(
                    inputs=flatten_,
                    num_outputs=1,
                    activation_fn=None,
                    weights_initializer=layers.xavier_initializer(
                        uniform=False),
                    biases_initializer=tf.zeros_initializer(),
                    scope=scope
                )
                print(linear_result)
            return linear_result

    def __loss_fn(self, X, G_sample, fake_scores, real_scores, penalty_lambda):
        """ C loss
        """
        with tf.name_scope('C_loss') as scope:
            # grad_pen, base on paper (Improved WGAN)
            epsilon = tf.random_uniform(
                [self.batch_size, 1, 1], minval=0.0, maxval=1.0)
            X_inter = epsilon * X + (1.0 - epsilon) * G_sample

            grad = tf.gradients(
                self.inference(X_inter, self.__matched_cond, reuse=True), [X_inter])[0]
            print(grad)
            sum_ = tf.reduce_sum(tf.square(grad), axis=[1, 2])
            print(sum_)
            grad_norm = tf.sqrt(sum_)
            grad_pen = penalty_lambda * tf.reduce_mean(
                tf.square(grad_norm - 1.0))
            f_fake = tf.reduce_mean(fake_scores)
            f_real = tf.reduce_mean(real_scores)

            loss = f_fake - f_real + grad_pen
        return loss, f_real, f_fake, grad_pen

    def step(self, sess, G_samples, real_data, conditions):
        """ train one batch on C
        """
        self.__steps += 1
        feed_dict = {self.__G_samples: G_samples,
                     self.__matched_cond: conditions,
                     self.__X: real_data}
        loss, global_steps, _ = sess.run(
            [self.__loss, self.__global_steps, self.__train_op], feed_dict=feed_dict)
        if not self.if_log_histogram or self.__steps % 500 == 0:  # % 500 to save space
            summary = sess.run(self.__summary_op, feed_dict=feed_dict)
            # log
            self.summary_writer.add_summary(
                summary, global_step=global_steps)
        return loss, global_steps

    def log_valid_loss(self, sess, G_samples, real_data, conditions):
        """ one batch valid loss
        """
        feed_dict = {self.__G_samples: G_samples,
                     self.__matched_cond: conditions,
                     self.__X: real_data}
        loss, global_steps = sess.run(
            [self.__loss, self.__global_steps], feed_dict=feed_dict)
        if not self.if_log_histogram or self.__steps % 500 == 0:  # % 500 to save space
            summary = sess.run(self.__summary_valid_op, feed_dict=feed_dict)
            # log
            self.valid_summary_writer.add_summary(
                summary, global_step=global_steps)
        return loss
