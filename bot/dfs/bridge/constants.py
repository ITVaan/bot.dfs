# -*- coding: utf-8 -*-

import os

from pytz import timezone

major = 0
minor = 0
bugfix = 1
version = '{}.{}.{}'.format(major, minor, bugfix)
author = "SfsBot"
retry_mult = 1
id_passport_len = 9
scheme = u'UA-EDR'
tender_status = "active.qualification"
DOC_TYPE = "sfsConfirmation"
AWARD_STATUS = 'active'
FORM_NAME = "Jxxxxxxx"
qualification_procurementMethodType = ('aboveThresholdUA', 'aboveThresholdUA.defense', 'aboveThresholdEU',
                                       'competitiveDialogueUA.stage2', 'competitiveDialogueEU.stage2')
HOLIDAYS_FILE = 'working_days.json'
TZ = timezone(os.environ['TZ'] if 'TZ' in os.environ else 'Europe/Kiev')
file_name = "sfs_reference.yaml"
