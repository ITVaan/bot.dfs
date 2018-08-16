# coding=utf-8
import os
import xmlschema
import logging.config
import datetime
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
    htin.text = u'02426097'
    hfill = SubElement(request, "HFILL")
    hfill.text = str(datetime.date.today())
    htime = SubElement(request, "HTIME")
    htime.text = str(datetime.datetime.now().time().replace(microsecond=0))
    hname = SubElement(request, "HNAME")
    hname.text = u'ДП «ПРОЗОРРО»'
    hksti = SubElement(request, "HKSTI")
    hksti.text = str(2659)
    hsti = SubElement(request, "HSTI")
    hsti.text = u'ДПI у Шевченківському районі ГУ ДФС у м.Києві'
    r0101g1s = SubElement(request, "R0101G1S")
    r0101g1s.text = data.tender_id
    r0201g1s = SubElement(request, "R0201G1S")
    r0201g1s.text = data.code
    r0202g1s = SubElement(request, "R0202G1S")
    if r0201g1s.text == data.code:
        r0202g1s.text = data.name
    r0203g1s = SubElement(request, "R0203G1S")
    r0204g1s = SubElement(request, "R0204G1S")
    r0205g1s = SubElement(request, "R0205G1S")
    if data.is_physical:
        r0203g1s.text = data.first_name
        r0204g1s.text = data.last_name
        r0205g1s.text = data.family_name

    logger.info("Request {} is valid? {}".format(request_id, is_valid(request)))


def form_yaml_from_response():
    return {"data": "placeholder"}
