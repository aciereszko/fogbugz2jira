# sorry, this script is ugly, it just needed to do what I wanted to do, feel free to just take it and make it your own
# This script exports all your fogbugz bugs to a JIRA readable JSON, along with comments and attachments

import json
import os

from fogbugz import FogBugz

S_FOGBUGZ_URL = '<your fogbugz url here>'
S_EMAIL = '<your user email here>'
S_PASSWORD = '<your password here>'
# fogbugz api access token so attachemnts can be retrieved by JIRA
S_TOKEN = '<your api access token here>'
# a hack to get around that I wanted to author to be a user in our project, user did not make his email public, this was the only way to associate the bugs
S_USER = '557058:40ea6b91-0dd5-4f6d-b3fb-351471ae1ef5'
MAX_BUGS = 9999
# Set this to bug number if you want to export just 1 bug
EXPORT_BUG = 0
# JIRA has file limits, this is a quick hack to keep it under the 10MB that jira handles - ugly
BATCH_SIZE = 900
LONG_BODY_COMMENTS = []


def get_attribute(bug, attribute):
    if hasattr(bug, attribute):
        return getattr(bug, attribute).string
    return ""


def get_date_created(bug):
    for fbevent in bug.events.findAll('event'):
        return get_attribute(fbevent, "dt")

    return ""


def get_events(bug, issue, BACKUP_DIR):
    events = []

    for fbevent in bug.events.findAll('event'):
        event = {}

        event['created'] = get_attribute(fbevent, "dt")
        eventBody = get_attribute(fbevent, "s")
        newBodies = []
        if eventBody is not None:
            eventBodyLength, bodyLengthSize = len(
                eventBody), 20000  # body comment message limit is 32KB, not counting whitespace, arbitraty number under this chosen
            newBodies = [eventBody[i:i + bodyLengthSize] for i in range(0, eventBodyLength, bodyLengthSize)]
            event['body'] = newBodies[0]

            if len(newBodies) > 1:
                global LONG_BODY_COMMENTS
                LONG_BODY_COMMENTS.append((issue['externalId'], len(eventBody)))
                print("Long body found!!")

        event['author'] = S_USER

        for fbatt in fbevent.rgAttachments:
            str1 = fbatt.sURL.string
            # print(str1)
            str2 = 'ixAttachment='
            loc1 = str1.find(str2) + len(str2)
            loc2 = str1.find('&amp;sFileName')

            str3 = ';sFileName='
            loc3 = str1.find(str3) + len(str3)
            loc4 = str1.find('&sTicket')

            theURL = S_FOGBUGZ_URL  # + att.sURL.string
            theURL += '/default.asp?'
            theURL += 'pg=pgDownload&pgType=pgFile'
            theURL += '&ixAttachment=' + str1[loc1:loc2]
            theURL += '&sFilename=' + str1[loc3:loc4]
            theURL += '&token=' + str(S_TOKEN)

            # fix the replace
            if fbatt.sFileName.string is not None:
                newFileName = fbatt.sFileName.string.replace('\\', '')
                newFileName = newFileName.replace(':', '')
                # print(newFileName)
                # print(theURL)

                issue['attachments'].append(
                    {"name": newFileName, "attacher": event['author'], "created": event['created'], "uri": theURL})

                # attachment_dir = BACKUP_DIR + '/' + str(issue['externalId'])
                # if not os.path.exists(attachment_dir):
                #     os.makedirs(attachment_dir)
                #
                # urllib.urlretrieve(theURL, attachment_dir + '/' + newFileName)

        events.append(event)

        for i in range(1, len(newBodies)):
            events.append({'created': event['created'], 'author': event['author'], 'body': newBodies[i]})

    return events


def dump_json(batch, counter, components, issues):
    print("Writing batch: " + str(counter))
    print("Found components: " + ''.join(str(e) for e in components))

    jira = {"projects": []}

    # hardcoded the project information
    project = {"name": "Support", "key": "SUP", "components": components, "issues": issues};

    jira['projects'].append(project)

    with open("jira_import_" + str(batch) + ".json", "w") as write_file:
        json.dump(jira, write_file)


def main():
    fb = FogBugz(S_FOGBUGZ_URL)
    fb.logon(S_EMAIL, S_PASSWORD)

    # how ugly is this, do we export one bug or all?
    if EXPORT_BUG != 0:
        resp = fb.search(q=str(EXPORT_BUG),
                         cols='ixBug',
                         max=MAX_BUGS)
    else:
        resp = fb.search(q='type:"Cases"',
                         cols='ixBug',
                         max=MAX_BUGS)

    cases = resp.cases.findAll('case')
    num_cases = len(cases)
    counter = 0
    batch = 1
    issues = []

    components = []

    BACKUP_DIR = os.getcwd() + '/' + 'attachments'

    for case in cases:
        counter += 1
        print("Processing case: " + str(counter) + " of " + str(num_cases))
        ixBug = int(case['ixBug'])
        print(ixBug)
        respBug = fb.search(q='%s' % ixBug,
                            cols='sTitle,sPersonAssignedTo,sProject,sArea,sCategory,sPriority,fOpen,events')
        xmlBug = respBug.cases.findAll('case')[0]

        issue = {}
        issue['externalId'] = int(xmlBug['ixBug'])
        issue['created'] = get_date_created(xmlBug)
        issue['summary'] = get_attribute(xmlBug, 'sTitle')
        issue['assignee'] = S_USER
        issue['reporter'] = S_USER
        component = get_attribute(xmlBug, 'sProject')
        issue['components'] = [component]
        # gathering all the components (Fogbugz projects) as we ecounter them
        if component not in components:
            components.append(component)
        issue['issueType'] = "Support"
        issue['priority'] = get_attribute(xmlBug, 'sPriority')
        issue['resolution'] = get_attribute(xmlBug, 'fOpen')
        issue['attachments'] = []
        issue['comments'] = get_events(xmlBug, issue, BACKUP_DIR)

        print(issue)
        print("Long body running count = " + str(len(LONG_BODY_COMMENTS)))
        print("Long body issues = " + str([c for c in LONG_BODY_COMMENTS]))

        issues.append(issue)

        if counter % BATCH_SIZE == 0:
            dump_json(batch, counter, components, issues)
            issues = []
            batch += 1

    # one last dump
    dump_json(batch, counter, components, issues)


main()
