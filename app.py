#!flask/bin/python
import os
import numpy as np
import tensorflow as tf
from PIL import Image
from werkzeug.utils import secure_filename
from flask import Flask, request, url_for, send_from_directory, jsonify, render_template
import time

#connect to cassandra
import logging
from cassandra.cluster import Cluster
from cassandra.query import SimpleStatement
cluster = Cluster(contact_points=['172.18.0.2'],port=9042)
session = cluster.connect()



# the model which does the prediction

from mnist import model

x = tf.placeholder("float", [None, 784])
sess = tf.Session()

with tf.variable_scope("regression"):
    y1, variables = model.regression(x)
saver = tf.train.Saver(variables)
saver.restore(sess, "mnist/ckpt/regression.ckpt")
print("load success")

def regression(input):
    return sess.run(y1, feed_dict={x: input}).flatten().tolist()

def predict(image_path):
    img = Image.open(image_path).convert('L')
    flatten_img = np.reshape(img, 784)
    input = np.array([1 - flatten_img])
    output = regression(input)
    return np.argmax(output)


#generate log
log = logging.getLogger()
log.setLevel('INFO')
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s[%(levelname)s] %(name)s: %(message)s"))
log.addHandler(handler)
#from cassandra.cluster import Cluster
#from cassandra import ConsistencyLevel

#create a table

KEYSPACE = "mykeyspace"

def createKeySpace():
  cluster = Cluster(contact_points=['172.18.0.2'],port=9042)
  session = cluster.connect()

  log.info("Creating keyspace...")
  try:
      session.execute("""
          CREATE KEYSPACE %s
          WITH replication = { 'class': 'SimpleStrategy', 'replication_factor': '2' }
          """ % KEYSPACE)

      log.info("setting keyspace...")
      session.set_keyspace(KEYSPACE)

      log.info("creating table...")
      session.execute("""
          CREATE TABLE mytable (
              mykey text,
              col1 text,
              col2 text,
              PRIMARY KEY (mykey,col1)
          )
          """)
  except Exception as e:
      log.error("Unable to create keyspace")
      log.error(e)

createKeySpace();


             
#insert data into database
def insert_into_cassandra(var1, var2, var3):
    sql = "INSERT INTO mykeyspace.mytable (mykey, col1, col2) VALUES ('%s', '%s', '%s');""" % (var1, var2, var3)
    session.execute(sql)


ALLOWED_EXTENSIONS = set(['png', 'jpg', 'jpeg', 'gif'])

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = os.getcwd() + '/upload/'


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1] in ALLOWED_EXTENSIONS


@app.route('/upload/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'],
                               filename)


@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        file = request.files['file']
        size = (28, 28)
        im = Image.open(file)
        im.thumbnail(size)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            im.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            file_url = url_for('uploaded_file', filename=filename)
            print(file_url)
            test_result = predict('.' + file_url)
            current=time.strftime("%Y/%m/%d %H:%M:%S")
            insert_into_cassandra(current,filename, test_result)
            print("Test result is {}".format(test_result))
            return render_template('base.html', result=test_result)
    return render_template('base.html')


if __name__ == '__main__':
    app.run(host='0.0.0.0',port=80,debug=80)


