import tensorflow as tf


def lstm_layer(inputs, lengths, state_size, keep_prob=1.0, scope='lstm-layer', reuse=False, return_final_state=False):
    """
    LSTM layer.
    Args:
        inputs: Tensor of shape [batch size, max sequence length, ...].
        lengths: Tensor of shape [batch size].
        state_size: LSTM state size.
        keep_prob: 1 - p, where p is the dropout probability.

    Returns:
        Tensor of shape [batch size, max sequence length, state_size] containing the lstm
        outputs at each timestep.
        
        cell_fw = tf.contrib.rnn.DropoutWrapper(
            tf.contrib.rnn.LSTMCell(
                state_size,
                reuse=reuse
            ),
            output_keep_prob=keep_prob
        )
        
    """

    cell_fw = tf.nn.RNNCellDropoutWrapper(
        tf.keras.layers.LSTMCell(units=state_size), 
        output_keep_prob=keep_prob)
    
    lstm_layer = tf.keras.layers.RNN(cell_fw, output_size=lengths, return_state=True)
    
    outputs, output_state = lstm_layer(inputs)

    if return_final_state:
        return outputs, output_state
    else:
        return outputs


    
    
class DenseLayer(tf.keras.layers.Layer):
    def __init__(self, *args, **kwargs):
        super(DenseLayer, self).__init__(*args, **kwargs)

    def build(self, inputs, output_units, bias=True, activation=None, batch_norm=None, dropout=None):
        print('Build dense layer')
        self.w = self.add_weight(
            shape=(shape(inputs, -1), output_units),
            dtype=tf.float32,
            initializer=tf.keras.initializers.VarianceScaling(),
            trainable=True)
    # Метод call будет иногда использоваться в режиме графа,
    # training превратится в тензор
    @tf.function
    def dense_layer(self, inputs, output_units, bias=False, activation=None, batch_norm=None, dropout=None, training=None):       
        print('Call dense layer')       
        #self.build(inputs, output_units)
        self.z = tf.matmul(inputs, self.w)
        
        if bias:
            self.b = self.add_weight(
                shape=(output_units),
                dtype=tf.float32,
                initializer=tf.constant_initializer(1),
                trainable=True)
            self.z = self.z + self.b   

        if batch_norm is not None:
            self.z = tf.keras.layers.BatchNormalization(self.z)

        self.z = activation(self.z) if activation else self.z
        self.z = tf.nn.dropout(self.z, dropout) if dropout is not None else self.z
        
        return self.z        


'''

def dense_layer2(inputs, output_units, bias=True, activation=None, batch_norm=None, dropout=None,
                scope='dense-layer', reuse=False):
    
    W = tf.Variable(shape=(shape(inputs, -1), output_units), initializer=tf.keras.initializers.VarianceScaling(), name="weights")    
    z = tf.matmul(inputs, W)
    
    if bias:
        b = tf.Variable(shape=(output_units), initializer = tf.keras.initializers.constant(), name='biases')               
        z = z + b   
    
    if batch_norm is not None:
        z = tf.keras.layers.BatchNormalization(z)

    z = activation(z) if activation else z
    z = tf.nn.dropout(z, dropout) if dropout is not None else z
    return z
    
'''


def temporal_convolution_layer(inputs, output_units, convolution_width, causal=False, dilation_rate=[1], bias=True,
                               activation=None, dropout=None, scope='causal-conv-layer', reuse=False):
    """
    Convolution over the temporal axis of sequence data.

    Args:
        inputs: Tensor of shape [batch size, max sequence length, input_units].
        output_units: Output channels for convolution.
        convolution_width: Number of timesteps to use in convolution.

    Returns:
        Tensor of shape [batch size, max sequence length, output_units].

    """
    with tf.variable_scope(scope, reuse=reuse):
        if causal:
            shift = (convolution_width / 2) + (int(dilation_rate[0] - 1) / 2)
            pad = tf.zeros([tf.shape(inputs)[0], shift, inputs.shape.as_list()[2]])
            inputs = tf.concat([pad, inputs], axis=1)

        W = tf.get_variable(
            name='weights',
            initializer=tf.contrib.layers.variance_scaling_initializer(),
            shape=[convolution_width, shape(inputs, 2), output_units]
        )

        z = tf.nn.convolution(inputs, W, padding='SAME', dilation_rate=dilation_rate)
        if bias:
            b = tf.get_variable(
                name='biases',
                initializer=tf.constant_initializer(),
                shape=[output_units]
            )
            z = z + b
        z = activation(z) if activation else z
        z = tf.nn.dropout(z, dropout) if dropout is not None else z
        z = z[:, :-shift, :] if causal else z
        return z


def time_distributed_dense_layer(inputs, output_units, bias=True, activation=None, batch_norm=None,
                                 dropout=None, scope='time-distributed-dense-layer', reuse=False):
    """
    Applies a shared dense layer to each timestep of a tensor of shape [batch_size, max_seq_len, input_units]
    to produce a tensor of shape [batch_size, max_seq_len, output_units].

    Args:
        inputs: Tensor of shape [batch size, max sequence length, ...].
        output_units: Number of output units.
        activation: activation function.
        dropout: dropout keep prob.

    Returns:
        Tensor of shape [batch size, max sequence length, output_units].

    """
    with tf.variable_scope(scope, reuse=reuse):
        W = tf.get_variable(
            name='weights',
            initializer=tf.contrib.layers.variance_scaling_initializer(),
            shape=[shape(inputs, -1), output_units]
        )
        z = tf.einsum('ijk,kl->ijl', inputs, W)
        if bias:
            b = tf.get_variable(
                name='biases',
                initializer=tf.constant_initializer(),
                shape=[output_units]
            )
            z = z + b

        if batch_norm is not None:
            z = tf.layers.batch_normalization(z, training=batch_norm, reuse=reuse)

        z = activation(z) if activation else z
        z = tf.nn.dropout(z, dropout) if dropout is not None else z
        return z





def sequence_log_loss(y, y_hat, sequence_lengths, max_sequence_length, eps=1e-15):
    y = tf.cast(y, tf.float32)
    y_hat = tf.minimum(tf.maximum(y_hat, eps), 1.0 - eps)
    log_losses = y*tf.log(y_hat) + (1.0 - y)*tf.log(1.0 - y_hat)
    sequence_mask = tf.cast(tf.sequence_mask(sequence_lengths, maxlen=max_sequence_length), tf.float32)
    avg_log_loss = -tf.reduce_sum(log_losses*sequence_mask) / tf.cast(tf.reduce_sum(sequence_lengths), tf.float32)
    return avg_log_loss


def sequence_rmse(y, y_hat, sequence_lengths, max_sequence_length):
    y = tf.cast(y, tf.float32)
    squared_error = tf.square(y - y_hat)
    sequence_mask = tf.cast(tf.sequence_mask(sequence_lengths, maxlen=max_sequence_length), tf.float32)
    avg_squared_error = tf.reduce_sum(squared_error*sequence_mask) / tf.cast(tf.reduce_sum(sequence_lengths), tf.float32)
    rmse = tf.sqrt(avg_squared_error)
    return rmse


def log_loss(y, y_hat, eps=1e-15):
    y = tf.cast(y, tf.float32)
    y_hat = tf.minimum(tf.maximum(y_hat, eps), 1.0 - eps)
    log_loss = -tf.reduce_mean(y*tf.log(y_hat) + (1.0 - y)*tf.log(1.0 - y_hat))
    return log_loss


def rank(tensor):
    """Get tensor rank as python list"""
    return len(tensor.shape.as_list())


def shape(tensor, dim=None):
    """Get tensor shape/dimension as list/int"""
    if dim is None:
        return tensor.shape.as_list()
    else:
        return tensor.shape.as_list()[dim]
