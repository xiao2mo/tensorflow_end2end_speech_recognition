#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""Bidirectional GRU-CTC model."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import tensorflow as tf
from .ctc_base import ctcBase


class BGRU_CTC(ctcBase):
    """Bidirectional GRU-CTC model.
    Args:
        batch_size: int, batch size of mini batch
        input_size: int, the dimensions of input vectors
        num_cell: int, the number of memory cells in each layer
        num_layer: int, the number of layers
        output_size: int, the number of nodes in softmax layer
            (except for blank class)
        parameter_init: A float value. Range of uniform distribution to
            initialize weight parameters
        clip_grad: A float value. Range of gradient clipping (> 0)
        clip_activation: not used
        dropout_ratio_input: A float value. Dropout ratio in input-hidden
            layers
        dropout_ratio_hidden: A float value. Dropout ratio in hidden-hidden
            layers
        num_proj: not used
        weight_decay: A float value. Regularization parameter for weight decay
        bottleneck_dim: not used
    """

    def __init__(self,
                 batch_size,
                 input_size,
                 num_cell,
                 num_layer,
                 output_size,
                 parameter_init=0.1,
                 clip_grad=None,
                 clip_activation=None,  # not used
                 dropout_ratio_input=1.0,
                 dropout_ratio_hidden=1.0,
                 num_proj=None,  # not used
                 weight_decay=0.0,
                 bottleneck_dim=None,  # not used
                 name='bgru_ctc'):

        ctcBase.__init__(self, batch_size, input_size, num_cell, num_layer,
                         output_size, parameter_init,
                         clip_grad, clip_activation,
                         dropout_ratio_input, dropout_ratio_hidden,
                         weight_decay, name)

    def define(self):
        """Construct model graph."""
        # Generate placeholders
        self._generate_placeholer()

        # Dropout for Input
        outputs = tf.nn.dropout(self.inputs,
                                self.keep_prob_input,
                                name='dropout_input')

        # Hidden layers
        for i_layer in range(self.num_layer):
            with tf.name_scope('BiGRU_hidden' + str(i_layer + 1)):

                initializer = tf.random_uniform_initializer(
                    minval=-self.parameter_init,
                    maxval=self.parameter_init)

                with tf.variable_scope('GRU', initializer=initializer):
                    gru_fw = tf.contrib.rnn.GRUCell(self.num_cell)
                    gru_bw = tf.contrib.rnn.GRUCell(self.num_cell)

                # Dropout (output)
                gru_fw = tf.contrib.rnn.DropoutWrapper(
                    gru_fw,
                    output_keep_prob=self.keep_prob_hidden)
                gru_bw = tf.contrib.rnn.DropoutWrapper(
                    gru_bw,
                    output_keep_prob=self.keep_prob_hidden)

                # _init_state_fw = gru_fw.zero_state(self.batch_size,
                #                                    tf.float32)
                # _init_state_bw = gru_bw.zero_state(self.batch_size,
                #                                    tf.float32)
                # initial_state_fw = _init_state_fw,
                # initial_state_bw = _init_state_bw,

                # Ignore 2nd return (the last state)
                (outputs_fw, outputs_bw), _ = tf.nn.bidirectional_dynamic_rnn(
                    cell_fw=gru_fw,
                    cell_bw=gru_bw,
                    inputs=outputs,
                    sequence_length=self.seq_len,
                    dtype=tf.float32,
                    scope='BiGRU_' + str(i_layer + 1))

                outputs = tf.concat(axis=2, values=[outputs_fw, outputs_bw])

        # Reshape to apply the same weights over the timesteps
        outputs = tf.reshape(outputs, shape=[-1, self.num_cell * 2])

        # `[batch_size, max_time, input_size_splice]`
        batch_size = tf.shape(self.inputs)[0]

        with tf.name_scope('output'):
            # Affine
            W_output = tf.Variable(tf.truncated_normal(
                shape=[self.num_cell * 2, self.num_classes],
                stddev=0.1, name='W_output'))
            b_output = tf.Variable(tf.zeros(
                shape=[self.num_classes], name='b_output'))
            logits_2d = tf.matmul(outputs, W_output) + b_output

            # Reshape back to the original shape
            logits_3d = tf.reshape(
                logits_2d, shape=[batch_size, -1, self.num_classes])

            # Convert to `[max_time, batch_size, num_classes]`
            self.logits = tf.transpose(logits_3d, (1, 0, 2))
