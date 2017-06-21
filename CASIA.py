import glob
import struct
import zipfile

from codecs import decode
from math import ceil
from os import listdir, makedirs, remove
from os.path import isdir, isfile
from time import clock
from urllib.request import urlretrieve

import numpy as np

from scipy.misc import toimage

from tqdm import tqdm

__author__ = 'Lucas Kjaero'


class CASIA:
    """
    Class to download and use data from the CASIA dataset. 
    """
    def __init__(self):
        assert get_all_datasets() is True, "Datasets aren't properly loaded, " \
                                       "rerun to try again or download datasets manually."
        self.datasets = {
            "competition-gnt": {
                "url": "http://www.nlpr.ia.ac.cn/databases/Download/competition/competition-gnt.zip",
                "type": "GNT",
            },
            "HWDB1.1trn_gnt_P1": {
                "url": "http://www.nlpr.ia.ac.cn/databases/Download/feature_data/HWDB1.1trn_gnt_P1.zip",
                "type": "GNT",
            },
            "HWDB1.1trn_gnt_P2": {
                "url": "http://www.nlpr.ia.ac.cn/databases/Download/feature_data/HWDB1.1trn_gnt_P2.zip",
                "type": "GNT",
            },
            "HWDB1.1tst_gnt": {
                "url": "http://www.nlpr.ia.ac.cn/databases/download/feature_data/HWDB1.1tst_gnt.zip",
                "type": "GNT",
            },
        }
        self.character_sets = [dataset for dataset in self.datasets if self.datasets[dataset]["type"] == "GNT"]

    def get_all_datasets(self):
        """
        Make sure the datasets are present. If not, downloads and extracts them.
        Attempts the download five times because the file hosting is unreliable.
        :return: True if successful, false otherwise
        """
        success = True

        for dataset in self.datasets:
            individual_success = self.get_dataset(dataset)
            if not individual_success:
                success = False

        return success

    def get_dataset(self, dataset):
        """
        Checks to see if the dataset is present. If not, it downloads and unzips it.
        """
        # If the dataset is present, no need to download anything.
        success = True
        if not isdir(dataset):

            # Try 5 times to download. The download page is unreliable, so we need a few tries.
            was_error = False
            for iteration in range(5):

                # Guard against trying again if successful
                if iteration == 0 or was_error is True:
                    zip_path = dataset + ".zip"

                    # Download zip files if they're not there
                    if not isfile(zip_path):
                        try:
                            with DLProgress(unit='B', unit_scale=True, miniters=1, desc=dataset) as pbar:
                                urlretrieve(self.datasets[dataset]["url"], zip_path, pbar.hook)
                        except Exception as ex:
                            print("Error downloading %s: %s" % (dataset, ex))
                            was_error = True

                    # Unzip the data files
                    if not isdir(dataset):
                        try:
                            with zipfile.ZipFile(zip_path) as zip_archive:
                                zip_archive.extractall(path=dataset)
                                zip_archive.close()
                        except Exception as ex:
                            print("Error unzipping %s: %s" % (zip_path, ex))
                            # Usually the error is caused by a bad zip file.
                            # Delete it so the program will try to download it again.
                            remove(zip_path)
                            was_error = True

            if was_error:
                print("\nThis recognizer is trained by the CASIA handwriting database.")
                print("If the download doesn't work, you can get the files at %s" % self.datasets[dataset]["url"])
                print("If you have download problems, "
                      "wget may be effective at downloading because of download resuming.")
                success = False

        return success

    def load_character_images(self):
        """
        Generator to load all images in the dataset. Yields (image, character) pairs until all images have been loaded.
        :return: (Pillow.Image.Image, string) tuples
        """
        for dataset in self.character_sets:
            assert self.get_dataset(dataset) is True, "Datasets aren't properly downloaded, " \
                                                 "rerun to try again or download datasets manually."

        for dataset in self.character_sets:
            for image, label in self.load_dataset(dataset):
                yield image, label

    def load_dataset(self, dataset):
        """
        Load a directory of gnt files. Yields the image and label in tuples.
        :param dataset: The directory to load.
        :return:  Yields (image, label) pairs. Pillow.Image.Image
        """
        assert self.get_dataset(dataset) is True, "Datasets aren't properly downloaded, " \
                                             "rerun to try again or download datasets manually."

        for path in glob.glob(dataset + "/*.gnt"):
            for image, label in load_gnt_file(path):
                yield image, label

    @staticmethod
    def load_gnt_file(filename, silent=False):
        """
        Load characters and images from a given GNT file.
        :param filename: The file path to load.
        :param silent: If not 
        :return: (image: np.array, character) tuples
        """
        if not silent:
            print("Loading file: %s" % filename)

        # Thanks to nhatch for the code to read the GNT file, available at https://github.com/nhatch/casia
        with open(filename, "rb") as f:
            while True:
                packed_length = f.read(4)
                if packed_length == b'':
                    break

                length = struct.unpack("<I", packed_length)[0]
                raw_label = struct.unpack(">cc", f.read(2))
                width = struct.unpack("<H", f.read(2))[0]
                height = struct.unpack("<H", f.read(2))[0]
                photo_bytes = struct.unpack("{}B".format(height * width), f.read(height * width))

                # Comes out as a tuple of chars. Need to be combined. Encoded as gb2312, gotta convert to unicode.
                label = decode(raw_label[0] + raw_label[1], encoding="gb2312")
                # Create an array of bytes for the image, match it to the proper dimensions, and turn it into a PIL image.
                image = toimage(np.array(photo_bytes).reshape(height, width))

                yield image, label


class DLProgress(tqdm):
    """ Class to show progress on dataset download """
    # Progress bar code adapted from a Udacity machine learning project.
    last_block = 0

    def __init__(self):
        self.total = 0

    def hook(self, block_num=1, block_size=1, total_size=None):
        self.total = total_size
        self.update((block_num - self.last_block) * block_size)
        self.last_block = block_num