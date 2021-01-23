#!/usr/bin/env python

import argparse
import zipfile
import xml.etree.ElementTree as etree
import re


def handleParameters():
    parser = argparse.ArgumentParser(description='Update series metadata in epub.')
    parser.add_argument('filename', metavar='EPUB_FILE', type=str,
                        help='epub file')
    parser.add_argument('series', metavar='SERIES_INFO', type=str,
                        help='Series info with format "Series Name:2"')
    args = parser.parse_args()
    return args


def parseSeries(series_data):
    """Series data is of the format "Name:number"""

    colon = series_data.rfind(':')
    if colon < 0:
        return series_data, None

    name = series_data[0:colon]
    number = series_data[colon+1:]
    return name, number
#


def findContent(zfile):
    """Find location of 'content.opf' file. This is stored in 'META-INF/container.xml'"""
    with zfile.open("META-INF/container.xml") as file:
        xml = etree.fromstring(file.read())
    #with

    return xml[0][0].attrib['full-path']        # <container> <rootfiles> <rootfile full-path="...">
#findContent


def addSeriesToMetadata(xml, series_title, series_number):
    """Find <metadata> element and add series info at the end."""

    # extract namespace from root element
    namespace = re.match(r'{.*}', xml.tag).group(0)  # namespace='{http://www.idpf.org/2007/opf}'
    ns = {'root': namespace[1:-1]}   # without the { }
    # now we can find the 'metadata' object
    metadata = xml.find('root:metadata', ns)
    if metadata == None:
        raise Exception("Can't find metadata object")
    #

    # add series info to metadata
    # <meta property="belongs-to-collection" id="c01">
    #     The Lord of the Rings
    # </meta>
    # <meta refines="#c01" property="collection-type">set</meta>
    # <meta refines="#c01" property="group-position">2</meta>
    meta = etree.SubElement(metadata, 'meta', {'property': 'belongs-to-collection', 'id':'series0'})
    meta.text = series_title
    meta = etree.SubElement(metadata, 'meta', {'refines': '#series0', 'property': 'collection-type'})
    meta.text = 'set'
    meta = etree.SubElement(metadata, 'meta', {'refines': '#series0', 'property': 'group-position'})
    meta.text = f'{series_number}'

    # Add series info to metadata in Calibre format
    # <meta name="calibre:series" content="The Lord of the Rings"/>
    # <meta name="calibre:series_index" content="2"/>
    meta = etree.SubElement(metadata, 'meta', {'name': 'calibre:series', 'content': series_title})
    meta = etree.SubElement(metadata, 'meta', {'name': 'calibre:series_index', 'content': series_number})
#


def updateZipFile(zip_filename, content_filename, elem_tree):
    new_zip_filename = zip_filename + '.new'
    # create a temp copy of the archive without filename
    with zipfile.ZipFile(zip_filename, 'r') as zin:
        with zipfile.ZipFile(new_zip_filename, 'w') as zout:
            zout.comment = zin.comment # preserve the comment
            for item in zin.infolist():
                if item.filename != content_filename:
                    zout.writestr(item, zin.read(item.filename))
                #
            #for
        #with
    #with

    with zipfile.ZipFile(new_zip_filename, 'a', compression=zipfile.ZIP_DEFLATED) as zout:
        with zout.open(content_filename, 'w') as file:
            elem_tree.write(file)
        #
    #
    print(f"New epub file: '{new_zip_filename}'")
#


def main():
    args = handleParameters()
    epub_filename = args.filename
    series_title, series_number = parseSeries(args.series)

    if series_number == None:
        print(f"ERROR: couldn't parse series info: '{args.series}'")
        return
    #

    try:
        zfile = zipfile.ZipFile(epub_filename)
        content_filename = findContent(zfile)
        #print(f"Found: {content_filename}")
    except FileNotFoundError:
        print(f"ERROR: File '{epub_filename}' not found. Bailing out.")
        return
    #try

    with zfile.open(content_filename) as file:
        xml = etree.fromstring(file.read())
    #with
    zfile.close()


    addSeriesToMetadata(xml, series_title, series_number)

    elem_tree = etree.ElementTree(xml)
    updateZipFile(epub_filename, content_filename, elem_tree)
#



if __name__ == "__main__":
    # execute only if run as a script
    main()
#if
