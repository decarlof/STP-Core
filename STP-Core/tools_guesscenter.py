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
# Last modified: Sept, 28th 2016
#

from math import pi
from numpy import float32, double, finfo, ndarray
from scipy.misc import imresize #scipy 0.12
from os import sep, remove
from os.path import basename
from sys import argv
from h5py import File as getHDF5

from pyfftw.interfaces.cache import enable as pyfftw_cache_enable, disable as pyfftw_cache_disable
from pyfftw.interfaces.cache import set_keepalive_time as pyfftw_set_keepalive_time

import time

import io.tdf as tdf
import utils.findcenter as findcenter
from utils.caching import cache2plan, plan2cache
from preprocess.extract_flatdark import extract_flatdark
from preprocess.flat_fielding import flat_fielding

from tifffile import imread, imsave # only for debug

def main(argv):          
	"""Try to guess the center of rotation of the input CT dataset.

    Parameters
    ----------
    infile  : array_like
        HDF5 input dataset

    outfile : string
        Full path where the identified center of rotation will be written as output

	scale   : int
        If sub-pixel precision is interesting, use e.g. 2.0 to get a center of rotation 
		of .5 value. Use 1.0 if sub-pixel precision is not required

	angles  : int
        Total number of angles of the input dataset	

	proj_from : int
        Initial projections to consider for the assumed angles

	proj_to : int
        Final projections to consider for the assumed angles

	method : string
		(not implemented yet)

	tmppath : string
        Temporary path where look for cached flat/dark files
       
    """ 	   
	# Get path:
	infile  = argv[0]          # The HDF5 file on the
	outfile = argv[1]          # The txt file with the proposed center
	scale   = float(argv[2])
	angles  = float(argv[3])
	proj_from  = int(argv[4])
	proj_to  = int(argv[5])
	method  = argv[6]
	tmppath = argv[7]	
	if not tmppath.endswith(sep): tmppath += sep	

	pyfftw_cache_disable()
	pyfftw_cache_enable()
	pyfftw_set_keepalive_time(1800)	

	# Create a silly temporary log:
	tmplog  = tmppath + basename(infile) + str(time.time())
			
	# Open the HDF5 file (take into account also older TDF versions):
	f_in = getHDF5( infile, 'r' )
	if "/tomo" in f_in:
		dset = f_in['tomo']
	else: 
		dset = f_in['exchange/data']
	num_proj = tdf.get_nr_projs(dset)	
	num_sinos = tdf.get_nr_sinos(dset)	

	# Get flats and darks from cache or from file:
	try:
		corrplan = cache2plan(infile, tmppath)
	except Exception as e:
		#print "Error(s) when reading from cache"
		corrplan = extract_flatdark(f_in, True, tmplog)
		remove(tmplog)
		plan2cache(corrplan, infile, tmppath)

	# Get first and the 180 deg projections: 	
	im1 = tdf.read_tomo(dset,proj_from).astype(float32)	

	idx = int(round( (proj_to - proj_from)/angles * pi)) + proj_from
	im2 = tdf.read_tomo(dset,idx).astype(float32)		

	# Apply simple flat fielding (if applicable):
	if (isinstance(corrplan['im_flat_after'], ndarray) and isinstance(corrplan['im_flat'], ndarray) and
		isinstance(corrplan['im_dark'], ndarray) and isinstance(corrplan['im_dark_after'], ndarray)) :		
		im1 = ((abs(im1 - corrplan['im_dark'])) / (abs(corrplan['im_flat'] - corrplan['im_dark']) 
			+ finfo(float32).eps)).astype(float32)	
		im2 = ((abs(im2 - corrplan['im_dark_after'])) / (abs(corrplan['im_flat_after'] - corrplan['im_dark_after']) 
			+ finfo(float32).eps)).astype(float32)	

	# Scale projections (if required) to get subpixel estimation:
	if ( abs(scale - 1.0) > finfo(float32).eps ):	
		im1 = imresize(im1, (int(round(scale*im1.shape[0])), int(round(scale*im1.shape[1]))), interp='bicubic', mode='F');	
		im2 = imresize(im2, (int(round(scale*im2.shape[0])), int(round(scale*im2.shape[1]))), interp='bicubic', mode='F');	

	# Find the center (flipping left-right im2):
	cen = findcenter.usecorrelation(im1, im2[ :,::-1])
	cen = cen / scale
	
	# Print center to output file:
	text_file = open(outfile, "w")
	text_file.write(str(int(cen)))
	text_file.close()
	
	# Close input HDF5:
	f_in.close()

if __name__ == "__main__":
	main(argv[1:])
