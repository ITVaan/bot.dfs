# coding=utf-8
import os
import xmlschema
import logging.config
from datetime import datetime
from xml.dom import minidom
from xml.etree import ElementTree
from xml.etree.ElementTree import Element, SubElement


logger = logging.getLogger(__name__)


def is_valid(request):
    schema = xmlschema.XMLSchema(os.path.join(os.getcwd(), "resources/request.xsd"))
    return schema.is_valid(request)


def prettify(elem):
    """Return a pretty-printed XML string for the Element.
    """
    rough_string = ElementTree.tostring(elem, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")


def form_xml_to_post(data, request_id):
    request = Element('request')
    hnum = SubElement(request, "HNUM")
    hnum.text = str(request_id)
    htin = SubElement(request, "HTIN")
    htin.text = str(data.code)
    hlnameu = SubElement(request, "HLNAMEU")
    hlname = SubElement(request, "HLNAME")
    hpname = SubElement(request, "HPNAME")
    hfname = SubElement(request, "HFNAME")
    if data.is_physical:
        hlname.text = data.last_name
        hpname.text = data.first_name
        hfname.text = data.family_name
    else:
        hlnameu.text = data.company_name
    id = SubElement(request, "ID")
    id.text = str(data.tender_id)
    hfill = SubElement(request, "HFILL")
    hfill.text = datetime.now().isoformat()
    logger.info("Request {} is valid? {}".format(request_id, is_valid(request)))


def form_yaml_from_response():
    return {"data": "placeholder"}
