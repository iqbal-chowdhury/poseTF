
# coding: utf-8

# In[ ]:

import numpy as np
import scipy,re
import math,h5py
# import caffe
from scipy import misc
from scipy import ndimage
import tensorflow as tf
import multiResData
import tempfile
import cv2
import PoseTrain
import localSetup
import myutils
import os
import cv2
from cvc import cvc
import math
import sys
import copy
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib import cm
from matplotlib.backends.backend_agg import FigureCanvasAgg


# In[ ]:

# not used anymore
# def scalepatches(patch,scale,num,rescale,cropsz):
#     sz = patch.shape
#     assert sz[0]%( (scale**(num-1))*rescale) is 0,"patch size isn't divisible by scale"
    
#     patches = []
#     patches.append(scipy.misc.imresize(patch[:,:,0],1.0/(scale**(num-1))/rescale))
#     curpatch = patch
#     for ndx in range(num-1):
#         sz = curpatch.shape
#         crop = int((1-1.0/scale)/2*sz[0])
# #         print(ndx,crop)
        
#         spatch = curpatch[crop:-crop,crop:-crop,:]
#         curpatch = spatch
#         sfactor = 1.0/(scale**(num-ndx-2))/rescale
#         tpatch = scipy.misc.imresize(spatch,sfactor,)
#         patches.append(tpatch[:,:,0])
#     return patches


# In[ ]:

def scaleImages(img,scale):
    sz = img.shape
    simg = np.zeros((sz[0],sz[1]/scale,sz[2]/scale,sz[3]))
    for ndx in range(sz[0]):
        for chn in range(sz[3]):
            simg[ndx,:,:,chn] = misc.imresize(img[ndx,:,:,chn],1./scale)

#     return simg
    zz = simg.astype('float')
    mm = zz.mean(1).mean(1)
    xx = zz-mm[:,np.newaxis,np.newaxis,:]
    return xx

def multiScaleImages(inImg, rescale, scale, l1_cropsz,conf):
    # only crop the highest res image
#     if l1_cropsz > 0:
#         inImg_crop = inImg[:,l1_cropsz:-l1_cropsz,l1_cropsz:-l1_cropsz,:]
#     else:
#         inImg_crop = inImg
            
    inImg = adjustContrast(inImg,conf)
    x0_in = scaleImages(inImg,rescale)
    x1_in = scaleImages(inImg,rescale*scale)
    x2_in = scaleImages(x1_in,scale)
    return x0_in,x1_in,x2_in

def multiScaleLabelImages(inImg, rescale, scale, l1_cropszf):
    # only crop the highest res image
#     if l1_cropsz > 0:
#         inImg_crop = inImg[:,l1_cropsz:-l1_cropsz,l1_cropsz:-l1_cropsz,:]
#     else:
#         inImg_crop = inImg
            
    x0_in = scaleImages(inImg,rescale)
    x1_in = scaleImages(inImg,rescale*scale)
    x2_in = scaleImages(x1_in,scale)
    return x0_in,x1_in,x2_in


# In[ ]:

def adjustContrast(inImg,conf):
    if conf.adjustContrast:
        clahe = cv2.createCLAHE(clipLimit=2.0,tileGridSize=(conf.clahegridsize,conf.clahegridsize))
        simg = np.zeros(inImg.shape)
        assert inImg.shape[3] == 1, 'cant adjust contrast on color images'
        for ndx in range(inImg.shape[0]):
            simg[ndx,:,:,0] = clahe.apply(inImg[ndx,...,0].astype('uint8')).astype('float')
        return simg
    else:
        return inImg


# In[ ]:

def processImage(framein,conf):
#     cropx = (framein.shape[0] - conf.imsz[0])/2
#     cropy = (framein.shape[1] - conf.imsz[1])/2
#     if cropx > 0:
#         framein = framein[cropx:-cropx,:,:]
#     if cropy > 0:
#         framein = framein[:,cropy:-cropy,:]
    framein = cropImages(framein,conf)
    framein = framein[np.newaxis,:,:,0:1]
    x0,x1,x2 = multiScaleImages(framein, conf.rescale,  conf.scale, conf.l1_cropsz)
    return x0,x1,x2
    


# In[ ]:

def cropImages(framein,conf):
    cshape = tuple(framein.shape[0:2])
    start = conf.cropLoc[cshape]  # cropLoc[0] should be for y.
    end = [conf.imsz[ndx] + start[ndx] for ndx in range(2)]
    return framein[start[0]:end[0],start[1]:end[1],:]


# In[ ]:

# def readLMDB(cursor,num,imsz,dataMod):
# #     imsz = conf.imsz
#     images = np.zeros((num,1,imsz[0],imsz[1]))
#     locs = []
#     datum = caffe.proto.caffe_pb2.Datum()

# #     print(images.shape)
#     for ndx in range(num):
#         if not cursor.next():
#             cursor.first()
# #             print('restarting at %d' % ndx)
            
#         value = cursor.value()
#         key = cursor.key()
#         datum.ParseFromString(value)
#         expname,curloc,t = dataMod.decodeID(cursor.key())

#         curlabel = datum.label
#         data = caffe.io.datum_to_array(datum)
#         images[ndx,0,:,:] = data.squeeze()
#         locs.append(curloc)
#     return images,locs



# In[1]:

def randomlyFlipLR(img,locs):
    num = img.shape[0]
    for ndx in range(num):
        jj = np.random.randint(2)
        if jj>0.5:
            img[ndx,...] = img[ndx,:,:,::-1]
            locs[ndx,:,0] = img.shape[3]-locs[ndx,:,0]
    return img,locs


# In[1]:

def randomlyFlipUD(img,locs):
    num = img.shape[0]
    for ndx in range(num):
        jj = np.random.randint(2)
        if jj>0.5:
            img[ndx,...] = img[ndx,:,::-1,:]
            locs[ndx,:,1] = img.shape[2]-locs[ndx,:,1]
    return img,locs


# In[2]:

def randomlyRotate(img,locs,conf):
    if conf.rrange<1:
        return img,locs
    num = img.shape[0]
    rows,cols = img.shape[2:]
    for ndx in range(num):
        rangle = (np.random.rand()*2-1)*conf.rrange
        ii = copy.deepcopy(img[ndx,...]).transpose([1,2,0])
        M = cv2.getRotationMatrix2D((cols/2,rows/2),rangle,1)
        ii = cv2.warpAffine(ii,M,(cols,rows))
        if ii.ndim==2:
            ii = ii[...,np.newaxis]
        ii = ii.transpose([2,0,1])
        img[ndx,...] = ii
        ll = copy.deepcopy(locs[ndx,...])
        ll = ll - [cols/2,rows/2]
        ang = np.deg2rad(rangle)
        R = [[np.cos(ang),-np.sin(ang)],[np.sin(ang),np.cos(ang)]]
        lr = np.dot(ll,R) + [cols/2,rows/2]
        locs[ndx,...] = lr
        
    return img,locs


# In[1]:

def randomlyAdjust(img,conf):
    # For images between 0 to 255 
    # and single channel
    num = img.shape[0]
    brange = conf.brange
    bdiff = brange[1]-brange[0]
    crange = conf.crange
    cdiff = crange[1]-crange[0]
    for ndx in range(num):
        mm = img[ndx,...].mean()
        bfactor = np.random.rand()*bdiff + brange[0]
        jj = img[ndx,...] + bfactor*255.0
        cfactor = np.random.rand()*cdiff + crange[0]
        jj = np.minimum(255,(jj-mm)*cfactor+mm)
        jj = jj.clip(0,255)
        img[ndx,...] = jj
    return img


# In[ ]:

# def readOnceLMDB(cursor,num,imsz,dataMod,reset=False):
#     images = np.zeros((0,1,imsz[0],imsz[1]))
#     locs = []
#     datum = caffe.proto.caffe_pb2.Datum()
    
#     if reset:
#         cursor.first()
        
#     done = False
#     for ndx in range(num):
#         if not cursor.next():
#             done = True
#             break
            
#         value = cursor.value()
#         key = cursor.key()
#         datum.ParseFromString(value)
#         expname,curloc,t = dataMod.decodeID(cursor.key())

#         curlabel = datum.label
#         data = caffe.io.datum_to_array(datum)
#         images = np.append(images,data.squeeze()[np.newaxis,:,:],0)
#         locs.append(curloc)
#     return images,locs,done



# In[ ]:

def blurLabel(imsz,loc,scale,blur_rad):
    sz0 = int(math.ceil(float(imsz[0])/scale))
    sz1 = int(math.ceil(float(imsz[1])/scale))

    label = np.zeros([sz0,sz1])
    if not np.isnan(loc[0]):
        label[int(loc[0]/scale),int(loc[1]/scale)] = 1
#         blurL = ndimage.gaussian_filter(label,blur_rad)
        ksize = 2*3*blur_rad+1
        blurL = cv2.GaussianBlur(label,(ksize,ksize),blur_rad)
        blurL = blurL/blurL.max()
    else:
        blurL = label
    return blurL


# In[ ]:

def createLabelImages(locs,imsz,scale,blur_rad):
    n_classes = len(locs[0])
    sz0 = int(math.ceil(float(imsz[0])/scale))
    sz1 = int(math.ceil(float(imsz[1])/scale))

    labelims = np.zeros((len(locs),sz0,sz1,n_classes))
    labelims1 = np.zeros((len(locs),sz0,sz1,n_classes))
    ksize = 3*blur_rad
    blurL = np.zeros([2*ksize+1,2*ksize+1])
    blurL[ksize,ksize] = 1
    blurL = cv2.GaussianBlur(blurL,(2*ksize+1,2*ksize+1),blur_rad)
    blurL = blurL/blurL.max()
    for cls in range(n_classes):
        for ndx in range(len(locs)):
#             modlocs = [locs[ndx][cls][1],locs[ndx][cls][0]]
#             labelims1[ndx,:,:,cls] = blurLabel(imsz,modlocs,scale,blur_rad)
            modlocs0 = int(np.round(locs[ndx][cls][1]/scale))
            modlocs1 = int(np.round(locs[ndx][cls][0]/scale))
            l0 = min(sz0,max(0,modlocs0-ksize))
            r0 = max(0,min(sz0,modlocs0+ksize+1))
            l1 = min(sz1,max(0,modlocs1-ksize))
            r1 = max(0,min(sz1,modlocs1+ksize+1))
            labelims[ndx,l0:r0,l1:r1,cls] = blurL[(l0-modlocs0+ksize):(r0-modlocs0+ksize),
                                                  (l1-modlocs1+ksize):(r1-modlocs1+ksize)]
 
    labelims = 2.0*(labelims-0.5)
    return labelims


# In[ ]:

def createRegLabelImages(locs,imsz,scale,blur_rad):
    n_classes = len(locs[0])
    sz0 = int(math.ceil(float(imsz[0])/scale))
    sz1 = int(math.ceil(float(imsz[1])/scale))

    labelims = np.zeros((len(locs),sz0,sz1,n_classes))
    regimsx = np.zeros((len(locs),sz0,sz1,n_classes))
    regimsy = np.zeros((len(locs),sz0,sz1,n_classes))
    for cls in range(n_classes):
        for ndx in range(len(locs)):
            x,y = np.meshgrid(np.arange(sz0),np.arange(sz1))
            modlocs = [locs[ndx][cls][1],locs[ndx][cls][0]]
            labelims[ndx,:,:,cls] = blurLabel(imsz,modlocs,scale,blur_rad)
            
#             np.sqrt((x-(round(locs[ndx][cls][0]/scale)))**2 + 
#                                (y-(round(locs[ndx][cls][1]/scale)))**2) < (rad-1)
#             xmin = int(max(round((locs[ndx][cls][0])/scale - rad),0))
#             xmax = int(min(round((locs[ndx][cls][0])/scale + rad),sz0))
#             ymin = int(max(round((locs[ndx][cls][1])/scale - rad),0))
#             ymax = int(min(round((locs[ndx][cls][1])/scale + rad),sz0))
#             labelims[ndx,ymin:ymax,xmin:xmax,cls] = 1.
            tx,ty = np.meshgrid(np.arange(sz0)*scale,np.arange(sz1)*scale)
            tregx = tx.astype('float64')
            tregy = ty.astype('float64')
            tregx = locs[ndx][cls][0] -1 - tregx
            tregy = locs[ndx][cls][1] -1 - tregy
            regimsx[ndx,:,:,cls] = tregx
            regimsy[ndx,:,:,cls] = tregy
            
    labelims = 2.0*(labelims-0.5)
    return labelims,regimsx,regimsy


# In[ ]:

def createFineLabelTensor(conf):
    tsz = int(conf.fine_sz + 2*6*math.ceil(conf.fine_label_blur_rad))
    timg = np.zeros((tsz,tsz))
    timg[tsz/2,tsz/2] = 1
    blurL = ndimage.gaussian_filter(timg,conf.fine_label_blur_rad)
    blurL = blurL/blurL.max()
    blurL = 2.0*(blurL-0.5)
    return tf.constant(blurL)


# In[ ]:

def extractFineLabelTensor(labelT,sz,dd,fsz):
    return tf.slice(labelT,dd+sz/2-fsz/2,[fsz,fsz])


# In[ ]:

def createFineLabelImages(locs,pred,conf,labelT):
    maxlocs = argmax2d(pred)*conf.pool_scale
    tsz = int(conf.fine_sz + 2*6*math.ceil(conf.fine_label_blur_rad))
    hsz = conf.fine_sz/2
    limgs = []
    for inum in range(conf.batch_size):
        curlimgs = []
        for ndx in range(conf.n_classes):
            dx = maxlocs[1,inum,ndx]-tf.to_int32(locs[inum,ndx,0]/conf.rescale)
            dy = maxlocs[0,inum,ndx]-tf.to_int32(locs[inum,ndx,1]/conf.rescale)
            dd = tf.pack([dx,dy])
            dd = tf.maximum(tf.to_int32(hsz-tsz/2),tf.minimum(tf.to_int32(tsz/2-hsz-1),dd))
            curlimgs.append(extractFineLabelTensor(labelT,tsz,dd,conf.fine_sz))
        limgs.append(tf.pack(curlimgs))
    return tf.transpose(tf.pack(limgs),[0,2,3,1])


# In[ ]:

def argmax2d(Xin):
    
    origShape = tf.shape(Xin)
    reshape_t = tf.concat(0,[origShape[0:1],[-1],origShape[3:4]])
    zz = tf.reshape(Xin,reshape_t)
    pp = tf.to_int32(tf.argmax(zz,1))
    sz1 = tf.slice(origShape,[2],[1])
    cc1 = tf.div(pp,tf.to_int32(sz1))
    cc2 = tf.mod(pp,tf.to_int32(sz1))
    
    return tf.pack([cc1,cc2])


# In[ ]:

def getBasePredLocs(pred,conf):
    predLocs = np.zeros([pred.shape[0],conf.n_classes,2])
    for ndx in range(pred.shape[0]):
        for cls in range(conf.n_classes):
            maxndx = np.argmax(pred[ndx,:,:,cls])
            curloc = np.array(np.unravel_index(maxndx,pred.shape[1:3]))
            curloc = curloc * conf.pool_scale * conf.rescale
            predLocs[ndx,cls,0] = curloc[1]
            predLocs[ndx,cls,1] = curloc[0]
    return predLocs


# In[ ]:

def getFinePredLocs(pred,finepred,conf):
    predLocs = np.zeros([pred.shape[0],conf.n_classes,2])
    finepredLocs = np.zeros([pred.shape[0],conf.n_classes,2])
    for ndx in range(pred.shape[0]):
        for cls in range(conf.n_classes):
            maxndx = np.argmax(pred[ndx,:,:,cls])
            curloc = np.array(np.unravel_index(maxndx,pred.shape[1:3]))
            curloc = curloc * conf.pool_scale * conf.rescale
            predLocs[ndx,cls,0] = curloc[1]
            predLocs[ndx,cls,1] = curloc[0]
            maxndx = np.argmax(finepred[ndx,:,:,cls])
            curfineloc = (np.array(np.unravel_index(maxndx,finepred.shape[1:3]))-conf.fine_sz/2)*conf.rescale
            finepredLocs[ndx,cls,0] = curloc[1] + curfineloc[1]
            finepredLocs[ndx,cls,1] = curloc[0] + curfineloc[0]
    return predLocs,finepredLocs


# In[ ]:

def getBaseError(locs,pred,conf):
    locerr = np.zeros(locs.shape)
    for ndx in range(pred.shape[0]):
        for cls in range(conf.n_classes):
            maxndx = np.argmax(pred[ndx,:,:,cls])
            predloc = np.array(np.unravel_index(maxndx,pred.shape[1:3]))
            predloc = predloc * conf.pool_scale * conf.rescale
            locerr[ndx][cls][0]= float(predloc[1])-locs[ndx][cls][0]
            locerr[ndx][cls][1]= float(predloc[0])-locs[ndx][cls][1]
    return locerr


# In[ ]:

def getFineError(locs,pred,finepred,conf):
    finelocerr = np.zeros([len(locs),conf.n_classes,2])
    baselocerr = np.zeros([len(locs),conf.n_classes,2])
    for ndx in range(pred.shape[0]):
        for cls in range(conf.n_classes):
            maxndx = np.argmax(pred[ndx,:,:,cls])
            predloc = np.array(np.unravel_index(maxndx,pred.shape[1:3]))
            predloc = predloc * conf.pool_scale * conf.rescale
            maxndx = np.argmax(finepred[ndx,:,:,cls])
            finepredloc = (np.array(np.unravel_index(maxndx,finepred.shape[1:3]))-conf.fine_sz/2)*conf.rescale
            baselocerr[ndx,cls,0]= float(predloc[1])-locs[ndx][cls][0]
            baselocerr[ndx,cls,1]= float(predloc[0])-locs[ndx][cls][1]
            finelocerr[ndx,cls,0]= float(predloc[1]+finepredloc[1])-locs[ndx][cls][0]
            finelocerr[ndx,cls,1]= float(predloc[0]+finepredloc[0])-locs[ndx][cls][1]
    return baselocerr,finelocerr


# In[ ]:

def initMRFweights(conf):
    L = h5py.File(conf.labelfile,'r')
    
    if 'pts' in L:
        pts = np.array(L['pts'])
        v = conf.view
    else:
        pp = np.array(L['labeledpos'])
        nmovie = pp.shape[1]
        pts = np.zeros([0,conf.n_classes,1,2])
        v = 0
        for ndx in range(nmovie):
            curpts = np.array(L[pp[0,ndx]])
            frames = np.where(np.invert( np.any(np.isnan(curpts),axis=(1,2))))[0]
            nptsPerView = np.array(L['cfg']['NumLabelPoints'])[0,0]
            pts_st = int(conf.view*nptsPerView)
            selpts = pts_st + conf.selpts
            curlocs = curpts[:,:,selpts]
            curlocs = curlocs[frames,:,:]
            curlocs = curlocs.transpose([0,2,1])
            pts = np.append(pts,curlocs[:,:,np.newaxis,:],axis=0)
            
            
    dx = np.zeros([pts.shape[0]])
    dy = np.zeros([pts.shape[0]])
    for ndx in range(pts.shape[0]):
        dx[ndx] = pts[ndx,:,v,0].max() - pts[ndx,:,v,0].min()
        dy[ndx] = pts[ndx,:,v,1].max() - pts[ndx,:,v,1].min()
    maxd = max( (numpy.percentile(dx,99), numpy.percentile(dy,99)))
    if hasattr(conf,'mrf_psz'):
        psz = conf.mrf_psz
        print('!!!Overriding MRF Size using conf.mrf_psz!!!')
        print('!!!Overriding MRF Size using conf.mrf_psz!!!')
        print('!!!Overriding MRF Size using conf.mrf_psz!!!')
    else:
        psz = int(math.ceil( (maxd*2/conf.rescale)/conf.pool_scale))
    bfilt = np.zeros([psz,psz,conf.n_classes,conf.n_classes])
    
    for ndx in range(pts.shape[0]):
        for c1 in range(conf.n_classes):
            for c2 in range(conf.n_classes):
                d12x = pts[ndx,c1,v,0] - pts[ndx,c2,v,0]
                d12y = pts[ndx,c1,v,1] - pts[ndx,c2,v,1]
                d12x = max(-psz/2+1,min(psz/2-1,int( (d12x/conf.rescale)/conf.pool_scale)))
                d12y = max(-psz/2+1,min(psz/2-1,int( (d12y/conf.rescale)/conf.pool_scale)))
                bfilt[psz/2+d12y,psz/2+d12x,c1,c2] += 1
    bfilt = (bfilt/pts.shape[0])
    return bfilt


# In[ ]:

def initMRFweightsIdentity(conf):
    L = h5py.File(conf.labelfile)
    pts = np.array(L['pts'])
    v = conf.view
    dx = np.zeros([pts.shape[0]])
    dy = np.zeros([pts.shape[0]])
    for ndx in range(pts.shape[0]):
        dx[ndx] = pts[ndx,:,v,0].max() - pts[ndx,:,v,0].min()
        dy[ndx] = pts[ndx,:,v,1].max() - pts[ndx,:,v,1].min()
    maxd = max(dx.max(),dy.max())
    hsz = int(math.ceil( (maxd*2/conf.rescale)/conf.pool_scale)/2)
    psz = hsz*2+1
#     psz = conf.mrf_psz
    bfilt = np.zeros([psz,psz,conf.n_classes,conf.n_classes])
    
    for c1 in range(conf.n_classes):
        bfilt[hsz,hsz,c1,c1] = 5.
    return bfilt


# In[ ]:

def getvars(vstr):
    varlist = tf.global_variables()
    blist = []
    for var in varlist:
        if re.match(vstr,var.name):
            blist.append(var)
    return blist


# In[ ]:

def compareConf(curconf,oldconf):
    ff = dir(curconf)
    for f in ff:
        if f[0:2] == '__' or f[0:3] == 'get':
            continue
        if hasattr(curconf,f) and hasattr(oldconf,f):
            if type(getattr(curconf,f)) is np.ndarray:
                print '%s'%(f)
                print 'New:' , getattr(curconf,f)
                print 'Old:' , getattr(oldconf,f)
            
            elif type(getattr(curconf,f)) is list:
                if type(getattr(oldconf,f)) is list:
                    if not cmp(getattr(curconf,f),getattr(oldconf,f)):
                        print '%s doesnt match'%(f)
                else:
                    print '%s doesnt match'%(f)
                
            elif getattr(curconf,f) != getattr(oldconf,f):
                print '%s doesnt match'%(f)
                
        else:
            print '%s doesnt match'%(f)
            


# In[ ]:

def createNetwork(conf,outtype):
    self = PoseTrain.PoseTrain(conf)
    self.createPH()
    self.createFeedDict()
    doBatchNorm = self.conf.doBatchNorm
    self.feed_dict[self.ph['phase_train_base']] = False
    self.feed_dict[self.ph['phase_train_fine']] = False
    self.feed_dict[self.ph['keep_prob']] = 1.
    self.feed_dict[self.ph['learning_rate']] = 0
    tt = self.ph['y'].get_shape().as_list()
    tt[0] = 1
    self.feed_dict[self.ph['y']] = np.zeros(tt)
    tt = self.ph['locs'].get_shape().as_list()
    self.feed_dict[self.ph['locs']] = np.zeros(tt)
    
    
    with tf.variable_scope('base'):
        self.createBaseNetwork(doBatchNorm)
    self.createBaseSaver()

    if outtype > 1:
        with tf.variable_scope('mrf'):
            self.createMRFNetwork(doBatchNorm)
        self.createMRFSaver()

    if outtype > 2:
        with tf.variable_scope('fine'):
            self.createFineNetwork(doBatchNorm)
        self.createFineSaver()

    return self


# In[ ]:

def initNetwork(self,sess,outtype):
    self.restoreBase(sess,True)
    if outtype > 1:
        self.restoreMRF(sess,True)
    if outtype > 2:
        self.restoreFine(sess,True)
    self.initializeRemainingVars(sess)


# In[ ]:

def openMovie(moviename):
    cap = cv2.VideoCapture(moviename)
    nframes = int(cap.get(cvc.FRAME_COUNT))
    return cap,nframes


# In[ ]:

def createPredImage(predscores,n_classes):
    im = np.zeros(predscores.shape[0:2]+(3,))
    im[:,:,0] = np.argmax(predscores,2).astype('float32')/(n_classes)*180
    im[:,:,1] = (np.max(predscores,2)+1)/2*255
    im[:,:,2] = 255.
    im = np.clip(im,0,255)
    im = im.astype('uint8')
    return cv2.cvtColor(im,cv2.COLOR_HSV2RGB) 
        


# In[ ]:

def classifyMovie(conf,moviename,outtype,self,sess,maxframes=-1):
    cap = cv2.VideoCapture(moviename)
    nframes = int(cap.get(cvc.FRAME_COUNT))
    if maxframes > 0:
        nframes = maxframes
    predLocs = np.zeros([nframes,conf.n_classes,2,2])
    predmaxscores = np.zeros([nframes,conf.n_classes,2])
    
    if outtype == 3:
        if self.conf.useMRF:
            predPair = [self.mrfPred,self.finePred]
        else:
            predPair = [self.basePred,self.finePred]
    elif outtype == 2:
        predPair = [self.mrfPred,self.basePred]
    else:        
        predPair = [self.basePred]
        
    bsize = conf.batch_size
    nbatches = int(math.ceil(float(nframes)/bsize))
#     framein = myutils.readframe(cap,1)
#     framein = cropImages(framein,conf)
#     framein = framein[np.newaxis,:,:,0:1]
#     x0t,x1t,x2t = multiScaleImages(framein, conf.rescale,  conf.scale, conf.l1_cropsz,conf)
#     clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(10,10))
#     print "WARNING!!!ATTENTION!!! DOING CONTRAST NORMALIZATION!!!!"
#     print "WARNING!!!ATTENTION!!! DOING CONTRAST NORMALIZATION!!!!"

    allf = np.zeros((bsize,)+conf.imsz+(1,))
    for curl in range(nbatches):
        
        ndxst = curl*bsize
        ndxe = min(nframes,(curl+1)*bsize)
        ppe = min(ndxe-ndxst,bsize)
        for ii in range(ppe):
            success,framein = cap.read()
            assert success, "Could not read frame"

            framein = cropImages(framein,conf)
#             framein = clahe.apply(framein[:,:,:1])
            allf[ii,...] = framein[...,0:1]
            
        x0,x1,x2 = multiScaleImages(allf, conf.rescale,  conf.scale, conf.l1_cropsz,conf)

        self.feed_dict[self.ph['x0']] = x0
        self.feed_dict[self.ph['x1']] = x1
        self.feed_dict[self.ph['x2']] = x2
        pred = sess.run(predPair,self.feed_dict)
        if curl == 0:
            predscores = np.zeros((nframes,)+pred[0].shape[1:] + (2,))
        if outtype == 3:
            baseLocs,fineLocs = getFinePredLocs(pred[0],pred[1],conf)
            predLocs[ndxst:ndxe,:,0,:] = fineLocs[:ppe,:,:]
            predLocs[ndxst:ndxe,:,1,:] = baseLocs[:ppe,:,:]
            for ndx in range(conf.n_classes):
                predmaxscores[ndxst:ndxe,:,0] = pred[0][:ppe,:,:,ndx].max()
                predmaxscores[ndxst:ndxe,:,1] = pred[1][:ppe,:,:,ndx].max()
            predscores[curl,:,:,:,0] = pred[0][:ppe,:,:,:]
        elif outtype == 2:
            baseLocs = getBasePredLocs(pred[0],conf)
            predLocs[ndxst:ndxe,:,0,:] = baseLocs[:ppe,:,:]
            baseLocs = getBasePredLocs(pred[1],conf)
            predLocs[ndxst:ndxe,:,1,:] = baseLocs[:ppe,:,:]
            for ndx in range(conf.n_classes):
                predmaxscores[ndxst:ndxe,:,0] = pred[0][:ppe,:,:,ndx].max()
                predmaxscores[ndxst:ndxe,:,1] = pred[1][:ppe,:,:,ndx].max()
            predscores[ndxst:ndxe,:,:,:,0] = pred[0][:ppe,:,:,:]
            predscores[ndxst:ndxe,:,:,:,1] = pred[1][:ppe,:,:,:]
        elif outtype == 1:
            baseLocs = getBasePredLocs(pred[0],conf)
            predLocs[ndxst:ndxe,:,0,:] = baseLocs[:ppe,:,:]
            for ndx in range(conf.n_classes):
                predmaxscores[ndxst:ndxe,:,0] = pred[0][:ppe,:,:,ndx].max()
            predscores[ndxst:ndxe,:,:,:,0] = pred[0][:ppe,:,:,:]
        sys.stdout.write('.')
        if curl%20==19:
            sys.stdout.write('\n')

    cap.release()
    return predLocs,predscores,predmaxscores


# In[ ]:

def createPredMovie(conf,predList,moviename,outmovie,outtype,maxframes=-1):
    
    predLocs,predscores,predmaxscores = predList
#     assert false, 'stop here'
    tdir = tempfile.mkdtemp()

    cap = cv2.VideoCapture(moviename)
    nframes = int(cap.get(cvc.FRAME_COUNT))
    if maxframes > 0:
        nframes = maxframes
    
    cmap = cm.get_cmap('jet')
    rgba = cmap(np.linspace(0,1,conf.n_classes))
    
    fig = mpl.figure.Figure(figsize = (9,4))
    canvas = FigureCanvasAgg(fig)
    
    if conf.adjustContrast:
        clahe = cv2.createCLAHE(clipLimit=2.0,tileGridSize=conf.clahegridsize)
    else:
        clahe = None
        
    for curl in range(nframes):
        framein = cv2.read()
        framein = cropImages(framein,conf)
        if framein.shape[2] > 1:
            framein = framein[...,0]
            
        if conf.adjustContrast:
            framein = clahe.apply(framein)

        fig.clf()
        ax1 = fig.add_subplot(1,2,1)
        ax1.imshow(framein, cmap=cm.gray)
        ax1.scatter(predLocs[curl,:,0,0],predLocs[curl,:,0,1], #hold=True,
                    c=cm.hsv(np.linspace(0,1-1./conf.n_classes,conf.n_classes)),
                    s=np.clip(predmaxscores[curl,:,0]*100,20,40),
                    linewidths=0,edgecolors='face')
        ax1.axis('off')
        ax2 = fig.add_subplot(1,2,2)
        if outtype == 1:
            curpreds = predscores[curl,:,:,:,0]
        elif outtype ==2:
            curpreds = predscores[curl,:,:,:,0]*2 - 1
            
        rgbim = createPredImage(curpreds,conf.n_classes)
        ax2.imshow(rgbim)
        ax2.axis('off')

        fname = "test_{:06d}.png".format(curl)
        
        # to printout without X. 
        # From: http://www.dalkescientific.com/writings/diary/archive/2005/04/23/matplotlib_without_gui.html
        # The size * the dpi gives the final image size
        #   a4"x4" image * 80 dpi ==> 320x320 pixel image
        canvas.print_figure(os.path.join(tdir,fname), dpi=160)
        
        # below is the easy way.
#         plt.savefig(os.path.join(tdir,fname))
        
    tfilestr = os.path.join(tdir,'test_*.png')
    mencoder_cmd = "mencoder mf://" + tfilestr +     " -frames " + "{:d}".format(nframes) + " -mf type=png:fps=15 -o " +     outmovie + " -ovc lavc -lavcopts vcodec=mpeg4:vbitrate=2000000"
    os.system(mencoder_cmd)
    cap.release()


# In[ ]:

def createPredMovieNoConf(conf,predList,moviename,outmovie,outtype):
    
    predLocs,predscores,predmaxscores = predList
#     assert false, 'stop here'
    tdir = tempfile.mkdtemp()

    cap = cv2.VideoCapture(moviename)
    nframes = int(cap.get(cvc.FRAME_COUNT))
    
    cmap = cm.get_cmap('jet')
    rgba = cmap(np.linspace(0,1,conf.n_classes))
    
    fig = mpl.figure.Figure(figsize = (9,4))
    canvas = FigureCanvasAgg(fig)
    for curl in range(nframes):
        framein = myutils.readframe(cap,curl)
        framein = cropImages(framein,conf)

        fig.clf()
        ax1 = fig.add_subplot(1,2,1)
        ax1.imshow(framein[:,:,0], cmap=cm.gray)
        ax1.scatter(predLocs[curl,:,0,0],predLocs[curl,:,0,1], #hold=True,
                    c=cm.hsv(np.linspace(0,1-1./conf.n_classes,conf.n_classes)),
                    s=20,linewidths=0,edgecolors='face')
        ax1.axis('off')
        ax2 = fig.add_subplot(1,2,2)
        if outtype == 1:
            curpreds = predscores[curl,:,:,:,0]
        elif outtype ==2:
            curpreds = predscores[curl,:,:,:,0]*2 - 1
            
        rgbim = createPredImage(curpreds,conf.n_classes)
        ax2.imshow(rgbim)
        ax2.axis('off')

        fname = "test_{:06d}.png".format(curl)
        
        # to printout without X. 
        # From: http://www.dalkescientific.com/writings/diary/archive/2005/04/23/matplotlib_without_gui.html
        # The size * the dpi gives the final image size
        #   a4"x4" image * 80 dpi ==> 320x320 pixel image
        canvas.print_figure(os.path.join(tdir,fname), dpi=80)
        
        # below is the easy way.
#         plt.savefig(os.path.join(tdir,fname))
        
    tfilestr = os.path.join(tdir,'test_*.png')
    mencoder_cmd = "mencoder mf://" + tfilestr +     " -frames " + "{:d}".format(nframes) + " -mf type=png:fps=15 -o " +     outmovie + " -ovc lavc -lavcopts vcodec=mpeg4:vbitrate=2000000"
    os.system(mencoder_cmd)
    cap.release()


# In[ ]:

def genDistortedImages(conf):
    self = PoseTrain.PoseTrain(conf)
    self.createPH()
    self.createFeedDict()
    self.trainType = 1
    self.openDBs()
    
    with tf.Session() as sess:

        self.createCursors(sess)
        for count in range(np.random.randint(50)):
            self.updateFeedDict(self.DBType.Train,sess=sess,distort=True)
    
    origImg = self.xs
    distImg = self.feed_dict[self.ph['x0']]
    return origImg,distImg,self.locs
        


# In[ ]:

def variable_summaries(var):
    """Attach a lot of summaries to a Tensor (for TensorBoard visualization)."""
    with tf.name_scope('summaries'):
        mean = tf.reduce_mean(var)
#         tf.summary.scalar('mean', mean)
        with tf.name_scope('stddev'):
            stddev = tf.sqrt(tf.reduce_mean(tf.square(var - mean)))
        tf.summary.scalar('stddev', stddev)
#         tf.summary.scalar('max', tf.reduce_max(var))
#         tf.summary.scalar('min', tf.reduce_min(var))
#         tf.summary.histogram('histogram', var)


# In[ ]:

def analyzeGradients(exclude):
    var = tf.global_variables()
    for vv in var:
        ("")

