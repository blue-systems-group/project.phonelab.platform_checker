PhoneLab Platform Sanity Checker
================================

Experimenters should pass this checker before notifying us that your experiment
changes are ready.

At high level, this script will check whether:

1. Your experiment changes can be merged into our develop branch
2. The platform (w/ your changes) can be build.

To pass the first one, we recommend you first merge our develop branch
(``phonelab/android-5.1.1_r3/develop``) into your experiment branch, so that the
reverse merge will be just a fast forward.


Usage:

.. code-block:: bash

    $ cd <AOSP_ROOT>
    $ source build/envsetup.sh
    $ lunch aosp_hammerhead-userdebug
    $ python checker.py --exp <EXPERIMENT_CODE_NAME>


Where ``<EXPERIMENT_CODE_NAME>`` is the last part in your experiment branch name.
