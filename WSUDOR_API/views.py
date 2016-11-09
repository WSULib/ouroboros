# -*- coding: utf-8 -*-
# WSUDOR_API

# Ouroboros config
import localConfig

# python modules
import json

# flask proper
from flask import render_template, request, session, redirect, make_response, Response

# WSUDOR_API_app
from WSUDOR_API import WSUDOR_API_app
from WSUDOR_API_main import WSUDOR_API_main
from WSUDOR_Manager.helpers import gzipped

