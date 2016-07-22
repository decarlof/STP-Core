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
# Last modified: July, 8th 2016
#

from sys import argv, exit
from os import remove, sep,  linesep
from os.path import exists
from numpy import float32, nanmin, nanmax, isscalar
from time import time
from multiprocessing import Process, Lock

from preprocess.extfov_correction import extfov_correction
from preprocess.flat_fielding import flat_fielding
from preprocess.ring_correction import ring_correction
from preprocess.extract_flatdark import extract_flatdark

from h5py import File as getHDF5
from utils.caching import cache2plan, plan2cache
import io.tdf as tdf

def main(argv):          
	"""To do...

	Usage
	-----
	

	Parameters
	---------
		   
	Example
	--------------------------
	The following line processes the first ten TIFF files of input path 
	"/home/in" and saves the processed files to "/home/out" with the 
	application of the Boin and Haibel filter with smoothing via a Butterworth
	filter of order 4 and cutoff frequency 0.01:

	destripe /home/in /home/out 1 10 1 0.01 4    

	"""
	lock = Lock()

	skip_ringrem = False
	skip_flat = False
	skip_flat_after = True
	first_done = False	

	# Get the number of sino to pre-process:
	idx = int(argv[0])
	   
	# Get paths:
	infile = argv[1]
	outfile = argv[2]
	
	# Normalization parameters:
	norm_sx = int(argv[3])
	norm_dx = int(argv[4])
	
	# Params for flat fielding with post flats/darks:
	flat_end = True if argv[5] == "True" else False
	half_half = True if argv[6] == "True" else False
	half_half_line = int(argv[7])
		
	# Params for extended FOV:
	ext_fov = True if argv[8] == "True" else False
	ext_fov_rot_right = argv[9]
	if ext_fov_rot_right == "True":
		ext_fov_rot_right = True
		if (ext_fov):
			norm_sx = 0
	else:
		ext_fov_rot_right = False
		if (ext_fov):
			norm_dx = 0		
	ext_fov_overlap = int(argv[10])
		
	# Method and parameters coded into a string:
	ringrem = argv[11]	
	
	# Tmp path and log file:
	tmppath = argv[12]	
	if not tmppath.endswith(sep): tmppath += sep		
	logfilename = argv[13]		

	
	# Open the HDF5 file:	
	f_in = getHDF5(infile, 'r')
	
	skipflat = False
	try:
		if "/tomo" in f_in:
			dset = f_in['tomo']		
		else: 
			dset = f_in['exchange/data']
			prov_dset = f_in['provenance/detector_output']			
	
	except:
		skipflat = True
		
	num_proj = tdf.get_nr_projs(dset)
	num_sinos = tdf.get_nr_sinos(dset)
	
	# Check if the HDF5 makes sense:
	if (num_sinos == 0):
		log = open(logfilename,"a")
		log.write(linesep + "\tNo projections found. Process will end.")	
		log.close()			
		exit()		

	# Get flat and darks from cache or from file:
	skipflat = False
	try:
		corrplan = cache2plan(infile, tmppath)
	except Exception as e:
		#print "Error(s) when reading from cache"
		corrplan = extract_flatdark(f_in, flat_end, logfilename)
		if (isscalar(corrplan['im_flat']) and isscalar(corrplan['im_flat_after']) ):
			skipflat = True
		else:
			plan2cache(corrplan, infile, tmppath)					
			

	# Read input image:
	im = tdf.read_sino(dset,idx).astype(float32)		
	f_in.close()	

	# Perform pre-processing (flat fielding, extended FOV, ring removal):	
	if not skipflat:
		im = flat_fielding(im, idx, corrplan, flat_end, half_half, half_half_line, norm_sx, norm_dx)			
	im = extfov_correction(im, ext_fov, ext_fov_rot_right, ext_fov_overlap)
	if not skipflat:
		im = ring_correction (im, ringrem, flat_end, corrplan['skip_flat_after'], half_half, half_half_line, ext_fov)		
	else:
		im = ring_correction (im, ringrem, False, False, half_half, half_half_line, ext_fov)						
	
	# Write down reconstructed preview file (file name modified with metadata):		
	im = im.astype(float32)
	outfile = outfile + '_' + str(im.shape[1]) + 'x' + str(im.shape[0]) + '_' + str( nanmin(im)) + '$' + str( nanmax(im) )	
	im.tofile(outfile)

	# 255 C:\Temp\Pippo.tdf C:\Temp\pippo 0 0 True False 900 False False 0 rivers:3;0 C:\Temp C:\Temp\log_00.txt

	
if __name__ == "__main__":
	main(argv[1:])
