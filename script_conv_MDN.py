import tensorflow as tf
import PoseMDN
from stephenHeadConfig import conf as conf
import PoseTools
import edward as ed
import math
import numpy as np
import matplotlib.pyplot as plt
import mymap
import PoseTrain
import os
import pickle
from tensorflow.contrib import slim
from edward.models import Categorical, Mixture, Normal, MultivariateNormalDiag
import copy

os.environ['CUDA_VISIBLE_DEVICES'] = '0'

conf.mdn_min_sigma = 3.
conf.mdn_max_sigma = 4.
conf.expname = 'head_conv_myloss'


tf.reset_default_graph()
restore = True
trainType = 0
conf.batch_size = 16
conf.nfcfilt = 256
self = PoseMDN.PoseMDN(conf)

mdn_dropout = 0.95
self.create_ph()
self.createFeedDict()
self.feed_dict[self.ph['keep_prob']] = mdn_dropout
self.feed_dict[self.ph['phase_train_base']] = False
self.feed_dict[self.ph['phase_train_mdn']] = True
self.feed_dict[self.ph['learning_rate']] = 0.
self.trainType = trainType

self.ph['base_pred'] = tf.placeholder(
    tf.float32, [None, 128, 128, self.conf.n_classes])

self.create_network_conv(self.ph['base_pred'])
self.openDBs()
self.create_saver()

y_label = self.ph['base_locs'] / self.conf.rescale / self.conf.pool_scale
self.mdn_label = y_label
# data_dict = {}
# for ndx in range(self.conf.n_classes):
#     data_dict[y[ndx]] = y_label[:, ndx, :]
# inference = mymap.MAP(data=data_dict)
# inference.initialize(var_list=PoseTools.getvars('mdn'))
self.loss = self.my_loss()

# # old settings
starter_learning_rate = 0.0001
decay_steps = 5000 / 8 * self.conf.batch_size
learning_rate = tf.train.exponential_decay(
    starter_learning_rate, self.ph['step'], decay_steps, 0.9,
    staircase=True)

# # new settings
# starter_learning_rate = 0.0001
# decay_steps = 12000 * 8 / self.conf.batch_size
# learning_rate = tf.train.exponential_decay(
#     starter_learning_rate, self.ph['step'], decay_steps, 0.9)

# self.opt = tf.train.AdamOptimizer(
#     learning_rate=learning_rate).minimize(self.loss)

update_ops = tf.get_collection(tf.GraphKeys.UPDATE_OPS)
with tf.control_dependencies(update_ops):
    self.opt = tf.train.AdamOptimizer(
        learning_rate=learning_rate).minimize(self.loss)


config = tf.ConfigProto()
config.gpu_options.per_process_gpu_memory_fraction = 0.5
sess = tf.Session(config=config)

self.createCursors(sess)
self.updateFeedDict(self.DBType.Train, sess=sess, distort=True)
self.feed_dict[self.ph['base_locs']] = np.zeros([self.conf.batch_size,
                                                 self.conf.n_classes, 2])
sess.run(tf.global_variables_initializer())
self.restore(sess, restore)
# self.initializeRemainingVars(sess)

with open(os.path.join(conf.cachedir, 'base_predictions'),
          'rb') as f:
    train_data, test_data = pickle.load(f)

m_train_data = train_data
o_test_data = copy.deepcopy(test_data)
for ndx in range(len(test_data)):
    bpred_in = test_data[ndx][0]
    tr_ndx = np.random.choice(len(train_data))
    bpred_tr = train_data[tr_ndx][0]
    bpred_out = -1 * np.ones(bpred_in.shape)
    tr_locs = PoseTools.getBasePredLocs(bpred_tr, self.conf)/4
    in_locs = PoseTools.getBasePredLocs(bpred_in, self.conf)/4

    # training blobs test locations
    # for ex in range(bpred_in.shape[0]):
    #     for cls in range(bpred_in.shape[-1]):
    #         cur_sc = bpred_in[ex,:,:,cls]
    #         inxx = int(in_locs[ex,cls,0])
    #         inyy = int(in_locs[ex,cls,1])
    #         trxx = int(tr_locs[ex,cls,0])
    #         tryy = int(tr_locs[ex,cls,1])
    #         tr_sc = bpred_tr[ex,(tryy-10):(tryy+10),
    #                 (trxx - 10):(trxx + 10),cls]
    #         bpred_out[ex,(inyy-10):(inyy+10),
    #             (inxx - 10):(inxx + 10),cls ] = tr_sc

    # test blobs training locs
    for ex in range(bpred_in.shape[0]):
        for cls in range(bpred_in.shape[-1]):
            cur_sc = bpred_in[ex,:,:,cls]
            inxx = int(in_locs[ex,cls,0])
            inyy = int(in_locs[ex,cls,1])
            trxx = int(tr_locs[ex,cls,0])
            tryy = int(tr_locs[ex,cls,1])
            test_sc = bpred_in[ex,(inyy-10):(inyy+10),
                    (inxx - 10):(inxx + 10),cls]
            bpred_out[ex,(tryy-10):(tryy+10),
                (trxx - 10):(trxx + 10),cls ] = test_sc
    test_data[ndx][0] = bpred_out
# m_test_data = [i for sl in zip(test_data,o_test_data) for i in sl]
m_test_data = o_test_data

self.updateFeedDict(self.DBType.Train, sess=sess,
                    distort=True)

mdn_steps = 50000 * 8 / self.conf.batch_size
test_step = 0

##

for cur_step in range(self.mdn_start_at, mdn_steps):
    self.feed_dict[self.ph['step']] = cur_step
    data_ndx = cur_step%len(m_train_data)
    cur_bpred = m_train_data[data_ndx][0]
    pd = 15
    cur_bpred = np.pad(cur_bpred,[[0,0],[pd,pd],[pd,pd],[0,0]],
                       'constant',constant_values=-1)
    dxx = np.random.randint(pd*2)
    dyy = np.random.randint(pd*2)
    cur_bpred = cur_bpred[:,dyy:(128+dyy),dxx:(128+dxx),:]
    # self.feed_dict[self.ph['step']] = step
    self.feed_dict[self.ph['base_locs']] = \
        PoseTools.getBasePredLocs(cur_bpred, self.conf)
    self.feed_dict[self.ph['base_pred']] = cur_bpred
    sess.run(self.opt, self.feed_dict)

    if cur_step % self.conf.display_step == 0:
        data_ndx = (cur_step+1) % len(m_train_data)
        cur_bpred = m_train_data[data_ndx][0]
        self.feed_dict[self.ph['base_locs']] = \
            PoseTools.getBasePredLocs(cur_bpred, self.conf)
        self.feed_dict[self.ph['base_pred']] = cur_bpred
        tr_loss = sess.run(self.loss, feed_dict=self.feed_dict)
        self.mdn_train_data['train_err'].append(tr_loss)
        self.mdn_train_data['step_no'].append(cur_step)

        mdn_pred = self.mdn_pred(sess)
        bee = PoseTools.getBaseError(
            self.feed_dict[self.ph['base_locs']], mdn_pred, conf)
        tt1 = np.sqrt(np.sum(np.square(bee), 2))
        nantt1 = np.invert(np.isnan(tt1.flatten()))
        train_dist = tt1.flatten()[nantt1].mean()
        self.mdn_train_data['train_dist'].append(train_dist)

        data_ndx = (test_step + 1) % len(m_test_data)
        cur_bpred = m_test_data[data_ndx][0]
        self.feed_dict[self.ph['base_locs']] = \
            PoseTools.getBasePredLocs(cur_bpred, self.conf)
        self.feed_dict[self.ph['base_pred']] = cur_bpred
        cur_te_loss = sess.run(self.loss, feed_dict=self.feed_dict)
        val_loss = cur_te_loss
        mdn_pred = self.mdn_pred(sess)
        bee = PoseTools.getBaseError(
            self.feed_dict[self.ph['base_locs']],mdn_pred,conf)
        tt1 = np.sqrt(np.sum(np.square(bee), 2))
        nantt1 = np.invert(np.isnan(tt1.flatten()))
        val_dist = tt1.flatten()[nantt1].mean()
        test_step += 1

        self.mdn_train_data['val_err'].append(val_loss)
        self.mdn_train_data['val_dist'].append(val_dist)

        print('{}:Train Loss:{:.4f},{:.2f}, Test Loss:{:.4f},{:.2f}'.format(
            cur_step, tr_loss, train_dist, val_loss, val_dist))

    if cur_step % self.conf.save_step == 0:
        self.save(sess, cur_step)

print("Optimization finished!")
self.save(sess, mdn_steps)
self.closeCursors()

