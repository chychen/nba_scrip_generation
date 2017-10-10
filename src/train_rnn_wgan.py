"""
data url: http://140.113.210.14:6006/NBA/data/NBA-TEAM1.npy
data description: 
    event by envet, with 300 sequence for each. (about 75 seconds)
    shape as [number of events, max sequence length, 33 dimensions(1 ball and 10 players x,y,z)]
    save it under the relative path './data/' before training
"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os
import time
import shutil
import numpy as np
import tensorflow as tf
import model_rnn_wgan
import game_visualizer


FLAGS = tf.app.flags.FLAGS

# path parameters
tf.app.flags.DEFINE_string('log_dir', 'v9/log/',
                           "summary directory")
tf.app.flags.DEFINE_string('checkpoints_dir', 'v9/checkpoints/',
                           "checkpoints dir")
tf.app.flags.DEFINE_string('sample_dir', 'v9/sample/',
                           "directory to save generative result")
tf.app.flags.DEFINE_string('data_path', '../data/NBA-ALL.npy',
                           "summary directory")
tf.app.flags.DEFINE_string('restore_path', None,
                           "path of saving model eg: checkpoints/model.ckpt-5")
# input parameters
tf.app.flags.DEFINE_integer('seq_length', 100,
                            "the maximum length of one training data")
tf.app.flags.DEFINE_integer('num_features', 23,
                            "3 (ball x y z) + 10 (players) * 2 (x and y)")
tf.app.flags.DEFINE_integer('latent_dims', 23,
                            "dimensions of latant variable")
# training parameters
tf.app.flags.DEFINE_integer('total_epoches', 3000,
                            "num of ephoches")
tf.app.flags.DEFINE_integer('num_train_D', 5,
                            "num of times of training D before train G")
tf.app.flags.DEFINE_integer('batch_size', 64,
                            "batch size")
tf.app.flags.DEFINE_float('learning_rate', 1e-4,
                          "learning rate")
tf.app.flags.DEFINE_integer('hidden_size', 23,
                            "hidden size of LSTM")
tf.app.flags.DEFINE_integer('rnn_layers', 2,
                            "num of layers for rnn")
tf.app.flags.DEFINE_float('penalty_lambda', 10.0,
                          "regularization parameter of wGAN loss function")
tf.app.flags.DEFINE_bool('if_feed_previous', False,
                         "if feed the previous output concated with current input")
tf.app.flags.DEFINE_integer('pretrain_epoches', 0,
                            "num of ephoch to train label as input")
# logging
tf.app.flags.DEFINE_integer('save_model_freq', 30,
                            "num of epoches to save model")
tf.app.flags.DEFINE_integer('save_result_freq', 10,
                            "num of epoches to save gif")
tf.app.flags.DEFINE_integer('log_freq', 100,
                            "num of steps to log")


class TrainingConfig(object):
    """
    Training config
    """

    def __init__(self):
        self.total_epoches = FLAGS.total_epoches
        self.batch_size = FLAGS.batch_size
        self.log_dir = FLAGS.log_dir
        self.checkpoints_dir = FLAGS.checkpoints_dir
        self.sample_dir = FLAGS.sample_dir
        self.data_path = FLAGS.data_path
        self.learning_rate = FLAGS.learning_rate
        self.hidden_size = FLAGS.hidden_size
        self.rnn_layers = FLAGS.rnn_layers
        self.save_model_freq = FLAGS.save_model_freq
        self.save_result_freq = FLAGS.save_result_freq
        self.log_freq = FLAGS.log_freq
        self.seq_length = FLAGS.seq_length
        self.num_features = FLAGS.num_features
        self.latent_dims = FLAGS.latent_dims
        self.penalty_lambda = FLAGS.penalty_lambda
        self.if_feed_previous = FLAGS.if_feed_previous
        self.num_train_D = FLAGS.num_train_D
        self.pretrain_epoches = FLAGS.pretrain_epoches

    def show(self):
        print("total_epoches:", self.total_epoches)
        print("batch_size:", self.batch_size)
        print("log_dir:", self.log_dir)
        print("checkpoints_dir:", self.checkpoints_dir)
        print("sample_dir:", self.sample_dir)
        print("data_path:", self.data_path)
        print("learning_rate:", self.learning_rate)
        print("hidden_size:", self.hidden_size)
        print("rnn_layers:", self.rnn_layers)
        print("save_model_freq:", self.save_model_freq)
        print("save_result_freq:", self.save_result_freq)
        print("log_freq:", self.log_freq)
        print("seq_length:", self.seq_length)
        print("num_features:", self.num_features)
        print("latent_dims:", self.latent_dims)
        print("penalty_lambda:", self.penalty_lambda)
        print("if_feed_previous:", self.if_feed_previous)
        print("num_train_D:", self.num_train_D)
        print("pretrain_epoches:", self.pretrain_epoches)


def z_samples():
    # TODO sample z from normal-distribution than
    return np.random.uniform(
        -1., 1., size=[FLAGS.batch_size, FLAGS.seq_length, FLAGS.latent_dims])


def training(sess, model, real_data, num_batches, saver, norm_dict, is_pretrain=False):
    """
    """
    if is_pretrain:
        num_epoches = FLAGS.pretrain_epoches
    else:
        num_epoches = FLAGS.total_epoches
    D_loss_mean = 0.0
    G_loss_mean = 0.0
    log_counter = 0
    # to evaluate time cost
    start_time = time.time()
    for epoch_id in range(num_epoches):
        # shuffle the data
        shuffled_indexes = np.random.permutation(real_data.shape[0])
        real_data = real_data[shuffled_indexes]

        batch_id = 0
        while batch_id < num_batches - FLAGS.num_train_D:
            real_data_batch = None
            # TODO make sure fairly train model on every batch
            if epoch_id < 30 or (epoch_id + 1) % 50 == 0:
                num_train_D = num_batches*5
            else:
                num_train_D = FLAGS.num_train_D
            for _ in range(num_train_D):
                # make sure not exceed the boundary
                data_idx = batch_id * \
                    FLAGS.batch_size % (real_data.shape[0] - FLAGS.batch_size)
                # data
                real_data_batch = real_data[data_idx:data_idx +
                                            FLAGS.batch_size]
                # train D
                D_loss_mean, global_steps = model.D_step(
                    sess, z_samples(), real_data_batch, is_pretrain)
                batch_id += 1
                log_counter += 1
            # train G
            G_loss_mean, global_steps = model.G_step(
                sess, z_samples(), is_pretrain, real_data_batch)
            log_counter += 1

            # logging
            if log_counter >= FLAGS.log_freq:
                end_time = time.time()
                log_counter = 0
                print("%d, epoches, %d steps, mean D_loss: %f, mean G_loss: %f, time cost: %f(sec)" %
                      (epoch_id,
                       global_steps,
                       D_loss_mean,
                       G_loss_mean,
                       (end_time - start_time)))
                start_time = time.time()  # save checkpoints
        # save model
        if (epoch_id % FLAGS.save_model_freq) == 0 or epoch_id == FLAGS.total_epoches - 1:
            save_path = saver.save(
                sess, FLAGS.checkpoints_dir + "model.ckpt",
                global_step=global_steps)
            print("Model saved in file: %s" % save_path)
        # plot generated sample
        if (epoch_id % FLAGS.save_result_freq) == 0 or epoch_id == FLAGS.total_epoches - 1:
            samples = model.generate(
                sess, z_samples(), is_pretrain, real_data_batch)
            # X
            samples[:, :, [0, 3, 5, 7, 9, 11, 13, 15, 17, 19, 21]] = samples[:, :, [
                0, 3, 5, 7, 9, 11, 13, 15, 17, 19, 21]] * norm_dict['x']['stddev'] + norm_dict['x']['mean']
            # Y
            samples[:, :, [1, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22]] = samples[:, :, [
                1, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22]] * norm_dict['y']['stddev'] + norm_dict['y']['mean']
            # Z
            samples[:, :, 2] = samples[:, :, 2] * \
                norm_dict['z']['stddev'] + norm_dict['z']['mean']
            game_visualizer.plot_data(
                samples, FLAGS.seq_length, file_path=FLAGS.sample_dir + str(global_steps) + '.gif', if_save=True)


def main(_):
    with tf.get_default_graph().as_default() as graph:
        # load data and remove useless z dimension of players in data
        real_data = np.load(FLAGS.data_path)[:, :FLAGS.seq_length, [
            0, 1, 2, 3, 4, 6, 7, 9, 10, 12, 13, 15, 16, 18, 19, 21, 22, 24, 25, 27, 28, 30, 31]]
        print('real_data.shape', real_data.shape)
        norm_dict = {}
        # X
        mean_x = np.mean(
            real_data[:, :, [0, 3, 5, 7, 9, 11, 13, 15, 17, 19, 21]])
        stddev_x = np.std(
            real_data[:, :, [0, 3, 5, 7, 9, 11, 13, 15, 17, 19, 21]])
        real_data[:, :, [0, 3, 5, 7, 9, 11, 13, 15, 17, 19, 21]] = (
            real_data[:, :, [0, 3, 5, 7, 9, 11, 13, 15, 17, 19, 21]] - mean_x) / stddev_x
        norm_dict['x']={}
        norm_dict['x']['mean'] = mean_x
        norm_dict['x']['stddev'] = stddev_x
        # Y
        mean_y = np.mean(
            real_data[:, :, [1, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22]])
        stddev_y = np.std(
            real_data[:, :, [1, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22]])
        real_data[:, :, [1, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22]] = (
            real_data[:, :, [1, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22]] - mean_y) / stddev_y
        norm_dict['y']={}
        norm_dict['y']['mean'] = mean_y
        norm_dict['y']['stddev'] = stddev_y
        # Z
        mean_z = np.mean(
            real_data[:, :, 2])
        stddev_z = np.std(
            real_data[:, :, 2])
        real_data[:, :, 2] = (
            real_data[:, :, 2] - mean_z) / stddev_z
        norm_dict['z']={}
        norm_dict['z']['mean'] = mean_z
        norm_dict['z']['stddev'] = stddev_z

        # number of batches
        num_batches = real_data.shape[0] // FLAGS.batch_size
        # config setting
        config = TrainingConfig()
        config.show()
        # model
        model = model_rnn_wgan.RNN_WGAN(config, graph)
        init = tf.global_variables_initializer()
        # saver for later restore
        saver = tf.train.Saver()

        with tf.Session() as sess:
            sess.run(init)
            # restore model if exist
            if FLAGS.restore_path is not None:
                saver.restore(sess, FLAGS.restore_path)
                print('successfully restore model from checkpoint: %s' %
                      (FLAGS.restore_path))
            # pre-training
            if FLAGS.pretrain_epoches > 0:
                training(sess, model, real_data, num_batches,
                         saver, norm_dict, is_pretrain=True)

            # training
            training(sess, model, real_data, num_batches, saver, norm_dict)


if __name__ == '__main__':
    if FLAGS.restore_path is None:
        # when not restore, remove follows (old) for new training
        if os.path.exists(FLAGS.log_dir):
            shutil.rmtree(FLAGS.log_dir)
            print('rm -rf "%s" complete!' % FLAGS.log_dir)
        if os.path.exists(FLAGS.checkpoints_dir):
            shutil.rmtree(FLAGS.checkpoints_dir)
            print('rm -rf "%s" complete!' % FLAGS.checkpoints_dir)
        if os.path.exists(FLAGS.sample_dir):
            shutil.rmtree(FLAGS.sample_dir)
            print('rm -rf "%s" complete!' % FLAGS.sample_dir)
    if not os.path.exists(FLAGS.checkpoints_dir):
        os.makedirs(FLAGS.checkpoints_dir)
    if not os.path.exists(FLAGS.sample_dir):
        os.makedirs(FLAGS.sample_dir)
    tf.app.run()
