﻿###########################################################################
# (C) 2016 Elettra - Sincrotrone Trieste S.C.p.A.. All rights reserved.   #
#                                                                         #
#                                                                         #
# This file is part of STP-Core, the Python core of SYRMEP Tomo Project,  #
# a software tool for the reconstruction of experimental CT datasets.     #
#                                                                         #
# STP-Core is free software: you can redistribute it and/or modify it     #
# under the terms of the GNU General Public License as published by the   #
# Free Software Foundation, either version 3 of the License, or (at your  #
# option) any later version.                                              #
#                                                                         #
# STP-Core is distributed in the hope that it will be useful, but WITHOUT #
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or   #
# FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License    #
# for more details.                                                       #
#                                                                         #
# You should have received a copy of the GNU General Public License       #
# along with STP-Core. If not, see <http://www.gnu.org/licenses/>.        #
#                                                                         #
###########################################################################

#
# Author: Francesco Brun
# Last modified: November, 2nd 2016
#

# TO DO: 
# - investigate the proper chunk size for performant I/O on both SSDs
#   and spinning disks.
# - check the newer versions of h5py (things changed in require_dataset)
#


import h5py
import numpy as np
import collections
import xml.etree.ElementTree as et

from numpy import isnan, isinf, nonzero, reshape, interp, float32, concatenate, zeros

DATA_ORDER = 1 # 0 for faster read/write projections, 1 for faster read/write sinograms, everything else for the other direction

def _remove_outliers ( im ):
	"""Correct NaN pixels by inteporlation

	Parameters
	----------
	im : array_like
		Image data as numpy array. 
	
	"""
	dt   = im.dtype
	im_f = im.flatten().astype(float32)	

	# Padding for better interpolation in case of outliers close to the margins:
	im_f = concatenate((zeros(1),im_f), axis=0)
	im_f = concatenate((im_f,zeros(1)), axis=0)	

	# Remove NaNs:
	val, x = isnan(im_f), lambda z: z.nonzero()[0]
	im_f[val] = interp(x(val), x(~val), im_f[~val])

	# Remove Infs:
	val, x = isinf(im_f), lambda z: z.nonzero()[0]
	im_f[val] = interp(x(val), x(~val), im_f[~val])

	# Reshape:
	im = reshape(im_f[1:-1], (im.shape[1], im.shape[0]), order='F').copy().T

	# Return:
	return im.astype(dt)

def parse_metadata( f, xml_command ):
	"""Fill the specified HDF5 file with metadata according to the DataExchange initiative.
	The metadata in input are described in a XML format.

	Parameters
	----------
	f : HDF5 file 
		HDF5 file open with h5py API
	xml_command : string
		Immaginary part of the complex X-ray refraction index.

	"""
	# Get XML structure from string:
	root = et.fromstring(xml_command)		
	
	# Create measurement group
	measurement  = f.create_group( 'measurement' )
	f.attrs['implements'] = "exchange:measurement:provenance"
	
	# Sample:
	sample =  measurement.create_group( 'sample' )	
	for el in root.findall('dataset'):				
		dset = sample.create_dataset('name', data = el.text)	
		
	# Instrument:
	instrument =  measurement.create_group( 'instrument' )		
	dset = instrument.create_dataset('name', data = 'SYRMEP')
	
	# Detector:
	detector = instrument.create_group('detector')	
	for el in root.findall('DETECTOR/model_name'):			
		dset = detector.create_dataset('model', data = el.text)
	#for el in root.findall('DETECTOR/exp_time'):			
	#	dset = detector.create_dataset('exposure_time', data = float(el.text)/1000.0, dtype = 'f')
	#	dset.attrs['units'] = 's'
	for el in root.findall('DETECTOR/bin'):			
		dset = detector.create_dataset('binning', data = int(el.text), dtype = 'i')		
	for el in root.findall('DETECTOR/remap'):			
		dset = detector.create_dataset('remapping', data = el.text)
	for el in root.findall('DETECTOR/pixel_size'):			
		val = str(el.text).split()
		dset = detector.create_dataset('pixel_size', data = float(val[0]), dtype = 'f')
		dset.attrs['units'] = val[1]
	roi = detector.create_group('roi')
	for el in root.findall('DETECTOR/left'):			
		dset = roi.create_dataset('x1', data = int(el.text), dtype= 'i')
		dset.attrs['units'] = 'pixels'
	for el in root.findall('DETECTOR/up'):			
		dset = roi.create_dataset('y1', data = int(el.text), dtype= 'i')
		dset.attrs['units'] = 'pixels'
	for el in root.findall('DETECTOR/right'):			
		dset = roi.create_dataset('x2', data = int(el.text), dtype= 'i')
		dset.attrs['units'] = 'pixels'
	for el in root.findall('DETECTOR/down'):			
		dset = roi.create_dataset('y2', data = int(el.text), dtype= 'i')
		dset.attrs['units'] = 'pixels'
		
	# Monochromator:
	monoch = instrument.create_group('monochromator')	
	for el in root.findall('MONOCH/energy_AA'):		
		dset = monoch.create_dataset('energy', data = int(el.text), dtype = 'i')
		dset.attrs['units'] = 'eV'
	for el in root.findall('MONOCH/berger_mono'):		
		dset = monoch.create_dataset('berger', data = int(el.text), dtype = 'i')
		dset.attrs['units'] = 'eV'
	for el in root.findall('MONOCH/AML_mono'):		
		dset = monoch.create_dataset('AML', data = int(el.text), dtype = 'i')		
		
	# Source:
	source = instrument.create_group('source')	
	for el in root.findall('RING/ring_current'):		
		val = str(el.text).split()
		dset = source.create_dataset('current', data = float(val[0]), dtype = 'f')
		dset.attrs['units'] = val[1]
	for el in root.findall('RING/ebeam_energy'):		
		val = str(el.text).split()
		dset = source.create_dataset('energy', data = float(val[0]), dtype = 'f')
		dset.attrs['units'] = val[1]	
	slits = source.create_group('slits')
	slits_air = slits.create_group('air')
	for el in root.findall('SLITS/slits_air_left'):			
		val = str(el.text).split()
		dset = slits_air.create_dataset('x1', data = float(val[0]), dtype = 'f')
		dset.attrs['units'] = val[1]
	for el in root.findall('SLITS/slits_air_up'):			
		val = str(el.text).split()
		dset = slits_air.create_dataset('y1', data = float(val[0]), dtype = 'f')
		dset.attrs['units'] = val[1]
	for el in root.findall('SLITS/slits_air_right'):			
		val = str(el.text).split()
		dset = slits_air.create_dataset('x2', data = float(val[0]), dtype = 'f')
		dset.attrs['units'] = val[1]
	for el in root.findall('SLITS/slits_air_down'):			
		val = str(el.text).split()
		dset = slits_air.create_dataset('y2', data = float(val[0]), dtype = 'f')
		dset.attrs['units'] = val[1]
	slits_vacuum = slits.create_group('vacuum')
	for el in root.findall('SLITS/slits_vacuum_left'):			
		val = str(el.text).split()
		dset = slits_vacuum.create_dataset('x1', data = float(val[0]), dtype = 'f')
		dset.attrs['units'] = val[1]
	for el in root.findall('SLITS/slits_vacuum_up'):			
		val = str(el.text).split()
		dset = slits_vacuum.create_dataset('y1', data = float(val[0]), dtype = 'f')
		dset.attrs['units'] = val[1]
	for el in root.findall('SLITS/slits_vacuum_right'):			
		val = str(el.text).split()
		dset = slits_vacuum.create_dataset('x2', data = float(val[0]), dtype = 'f')
		dset.attrs['units'] = val[1]
	for el in root.findall('SLITS/slits_vacuum_down'):			
		val = str(el.text).split()
		dset = slits_vacuum.create_dataset('y2', data = float(val[0]), dtype = 'f')
		dset.attrs['units'] = val[1]
		
def read_tomo( dataset, index ):
	"""Extract the tomographic projection at the specified relative index from the HDF5 dataset.

	Parameters
	----------
	dataset : HDF5 dataset 
		HDF5 dataset as returned by the h5py API.
	index : int
		Relative position of the tomographic projection within the dataset.

	"""
	
	#if (DATA_ORDER == 0):
	#	return dataset[index,:,:]	
	#elif (DATA_ORDER == 1):
	#	return dataset[:,index,:]	
	#else:
	#	return dataset[:,:,index]
	if (DATA_ORDER == 0):
		out = np.empty((dataset.shape[1],dataset.shape[2]), dtype=dataset.dtype)
		dataset.read_direct(out, np.s_[index,:,:])
		return _remove_outliers(out)
	else: # (DATA_ORDER == 1):	
		out = np.empty((dataset.shape[0],dataset.shape[2]), dtype=dataset.dtype)
		dataset.read_direct(out, np.s_[:,index,:])
		return _remove_outliers(out)

def read_sino( dataset, index ):
	"""Extract the sinogram at the specified relative index from the HDF5 dataset.

	Parameters
	----------
	dataset : HDF5 dataset 
		HDF5 dataset as returned by the h5py API.
	index : int
		Relative position of the sinogram within the dataset.

	"""

	#if (DATA_ORDER == 0):
	#	return dataset[:,index,:]	
	#elif (DATA_ORDER == 1):
	#	return dataset[index,:,:]		
	#else:
	#	return dataset[:,:,index]		
	if (DATA_ORDER == 0):
		out = np.empty((dataset.shape[0],dataset.shape[2]), dtype=dataset.dtype)
		dataset.read_direct(out, np.s_[:,index,:])		
		return _remove_outliers(out)
	else: # (DATA_ORDER == 1):
		out = np.empty((dataset.shape[1],dataset.shape[2]), dtype=dataset.dtype)
		dataset.read_direct(out, np.s_[index,:,:])
		return _remove_outliers(out)

def write_tomo( dataset, index, im ):
	"""Modify the tomographic projection at the specified relative index from the HDF5 dataset 
	with the image passed as input.

	Parameters
	----------
	dataset : HDF5 dataset 
		HDF5 dataset as returned by the h5py API.
	index : int
		Relative position of the tomographic projection within the dataset.
	im : array_like
		Image data as numpy array.

	"""
	if (DATA_ORDER == 0):
		dataset[index,:,:] = im	
	else: # (DATA_ORDER == 1):
		dataset[:,index,:] = im	

def write_sino( dataset, index, im ):
	"""Modify the sinogram at the specified relative index from the HDF5 dataset 
	with the image passed as input.

	Parameters
	----------
	dataset : HDF5 dataset 
		HDF5 dataset as returned by the h5py API.
	index : int
		Relative position of the sinogram within the dataset.
	im : array_like
		Image data as numpy array.

	"""
	if (DATA_ORDER == 0):
		dataset[:,index,:] = im
	else: # (DATA_ORDER == 1):
		dataset[index,:,:] = im		
	
def get_nr_projs ( dataset ):
	"""Get the number of projections of the input dataset.

	Parameters
	----------
	dataset : HDF5 dataset 
		HDF5 dataset as returned by the h5py API.

	"""
	if (DATA_ORDER == 0):
		return dataset.shape[0]	
	else: # (DATA_ORDER == 1):
		return dataset.shape[1]		
	
def get_nr_sinos ( dataset ):
	"""Get the number of sinograms (or slices) of the input dataset.

	Parameters
	----------
	dataset : HDF5 dataset 
		HDF5 dataset as returned by the h5py API.

	"""
	if (DATA_ORDER == 0):
		return dataset.shape[1]	
	else: # (DATA_ORDER == 1):
		return dataset.shape[0]	
		
def get_det_size ( dataset ):
	"""Get the width of the detector (nr of pixels) of the input dataset.

	Parameters
	----------
	dataset : HDF5 dataset 
		HDF5 dataset as returned by the h5py API.

	"""
	return dataset.shape[2]	
	
def get_dset_shape ( det_size, fov_height, nr_proj ):
	"""Get the shape of the dataset by arranging the input parameters.

	Parameters
	----------
	det_size : int
		Width of the detector.
	fov_height : int
		Height of the FOV, i.e. the number of sinograms (or slices) of the dataset.
	nr_proj : int
		Number of collected projections.

	"""
	if (DATA_ORDER == 0):
		return (nr_proj, fov_height, det_size)
	else: # (DATA_ORDER == 1):
		return (fov_height, nr_proj, det_size)		
		
def get_dset_chunks ( det_size ):
	"""Get a good chunk combination. This function needs improvement...

	Parameters
	----------
	det_size : int
		Width of the detector.	

	"""
	if (DATA_ORDER == 0):
		return (1, 1, det_size)
	else: # (DATA_ORDER == 1):
		return (1, 1, det_size)		
