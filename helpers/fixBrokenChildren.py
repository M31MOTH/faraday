#!/usr/bin/env python2.7
'''
Faraday Penetration Test IDE
Copyright (C) 2014  Infobyte LLC (http://www.infobytesec.com/)
See the file 'doc/LICENSE' for the license information

'''
'''
This script either updates or removes Interfaces, Services and Vulnerabilities in case their parent property is null.
If the property is null but a parent is found in Couch, the document is updated.
If the parent is not found in Couch the document is deleted, since it is an invalid one.
'''

import argparse
import json
import requests
import os
from pprint import pprint

def main():
    #arguments parser
    parser = argparse.ArgumentParser(prog='fixBrokenChildren', epilog="Example: ./%(prog)s.py")
    parser.add_argument('-c', '--couchdburi', action='store', type=str,
                        dest='couchdb',default="http://127.0.0.1:5984",
                        help='Couchdb URL (default http://127.0.0.1:5984)')
    parser.add_argument('-d', '--db', action='store', type=str,
                        dest='db', help='DB to process')

    #arguments put in variables
    args = parser.parse_args()
    dbs = list()

    #default value from ENV COUCHDB
    couchdb = os.environ.get('COUCHDB')
    #Else from argument
    if not couchdb:
        couchdb = args.couchdb

    if args.db:
        dbs.append(args.db)

    if len(dbs) == 0:
        dbs = requests.get(couchdb + '/_all_dbs')
        dbs = dbs.json()
        dbs = filter(lambda x: not x.startswith('_') and x != 'cwe' and x != 'reports', dbs)
    
    for db in dbs:
        fixDb(couchdb, db)

def fixDb(couchdb, db):
    couchdb = str(couchdb)
    db = str(db)

    #get all broken elements from CouchDB
    headers = {'Content-Type': 'application/json'}
    payload = { "map" : """function(doc) { if(doc.type == \"Interface\" ||
                                            doc.type == \"Service\" ||
                                            doc.type == \"Vulnerability\" ||
                                            doc.type == \"VulnerabilityWeb\"){ if(doc.parent == null) emit(doc.parent, 1); }}""" }

    r = requests.post(couchdb + '/' + db + '/_temp_view', headers=headers, data=json.dumps(payload))
    response_code = r.status_code

    if response_code == 200:
        response = r.json()
        rows = response['rows']
        rows = sorted(rows, key=lambda x: x['id'])

        if len(rows) > 0:
            print " [*[ Processing " + str(len(rows)) + " documents for " + db + " ]*]"

            for row in rows:
                id = str(row['id'])
                parent = str(id[:id.rfind('.')])

                parent_response = requests.get(couchdb + '/' + db + '/' + parent)
                parent_code = parent_response.status_code

                child_response = requests.get(couchdb + '/' + db + '/' + id)
                child = child_response.json()

                #object parent exists in Couch
                #update parent field in obj 
                if parent_code == 200:
                    print " - Updating " + child['type'] + " \"" + child['name'] + "\" with ID " + id
                    child['parent'] = parent
                    #print doc['parent']
                    update = requests.put(couchdb + '/' + db + '/' + id, headers=headers, data=json.dumps(child))
                    print " -- " + update.reason + " (" + str(update.status_code) + ")"

                #object has no valid parent
                #delete obj
                elif parent_code == 404:
                    # delete vuln
                    print " - Deleting " + child['type'] + " \"" + child['name'] + "\"  with ID " + id
                    delete = requests.delete(couchdb + '/' + db + '/' + id + '?rev=' + child['_rev'])
                    print " -- " + delete.reason + " (" + str(delete.status_code) + ")"
                elif parent_code == 401:
                    print " Autorization required, make sure to add user:pwd to Couch URI using --couchdburi"
                else:
                    print " Fail"
        else:
            print "Congratz, " + db + " is just fine!"
    elif response_code == 401:
        print " Autorization required to access " + db + ", make sure to add user:pwd to Couch URI using --couchdburi"

if __name__ == "__main__":
    main()
