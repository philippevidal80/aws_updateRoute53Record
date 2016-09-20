# -*- coding:utf-8 -*-

from __future__ import print_function

import boto3, json, re, argparse, sys, ipaddress

HOSTED_PUB_ZONE_ID = 'ZEFWBZI2V4FHZ'
HOSTED_PRIV_ZONE_ID = 'Z1CXVUI9TL20L0'
HOSTED_REV_PRIV_ZONE_ID = 'Z1DYAE7M4693LL'
HOSTED_PRIV_ZONE_NAME = 'sgp.pop.prosodie.com'
HOSTED_PUB_ZONE_NAME = 'sgp.pop.prosodie.com'

def reverse(ip):
    if ip.version == 6:
        ipexp = ip.exploded[::-1].replace(':', '')
    else:
        ipexp = ip.exploded.split('.')[::-1]

    temp = ""
    for i in ipexp:
        temp = temp + i + "."

    if ip.version == 6:
        return "{}ip6.arpa.".format(temp)
    else:
        return "{}in-addr.arpa.".format(temp)

def search(dicts, search_for):
    for item in dicts:
        if search_for == item['Key']:
            return item['Value']
    return None


def is_valid_hostname(hostname):
    if len(hostname) > 255:
        return False
    if hostname[-1] == ".":
        hostname = hostname[:-1]
    allowed = re.compile("(?!-)[A-Z\d-]{1,63}(?<!-)$", re.IGNORECASE)
    return all(allowed.match(x) for x in hostname.split("."))


def handler(event, context):
    ec2 = boto3.resource('ec2')
    route53 = boto3.client('route53')

    instance_id = event['detail']['instance-id']
    instance = ec2.Instance(instance_id)
    instance_ip = instance.private_ip_address
    instance_ip_pub = instance.public_ip_address
    instance_name = search(instance.tags, 'Name')
    instance_pub_name = search(instance.tags, 'Public Name')
    instance_ip_rev = reverse(ipaddress.ip_address(unicode(instance_ip)))

    print("Processing: {0}".format(instance_id))

    if not is_valid_hostname("{0}".format(instance_name)):
        print("Invalid hostname! No changes made.")
        return {'status': "Invalid hostname"}

    dns_changes_priv_pub = {
        'Changes': [
            {
                'Action': 'UPSERT',
                'ResourceRecordSet': {
                    'Name': "{0}.private.{1}.".format(instance_name, HOSTED_PRIV_ZONE_NAME),
                    'Type': 'A',
                    'ResourceRecords': [
                        {
                            'Value': instance_ip
                        }
                    ],
                    'TTL': 300
                }
            }
        ]
    }

    dns_changes_priv = {
        'Changes': [
            {
                'Action': 'UPSERT',
                'ResourceRecordSet': {
                    'Name': "{0}.{1}.".format(instance_name, HOSTED_PRIV_ZONE_NAME),
                    'Type': 'A',
                    'ResourceRecords': [
                        {
                            'Value': instance_ip
                        }
                    ],
                    'TTL': 300
                }
            }
        ]
    }

    dns_changes_priv_rev = {
        'Changes': [
            {
                'Action': 'UPSERT',
                'ResourceRecordSet': {
                    'Name': "{0}".format(instance_ip_rev),
                    'Type': 'PTR',
                    'ResourceRecords': [
                        {
                            'Value': "{0}.{1}.".format(instance_name, HOSTED_PRIV_ZONE_NAME)
                        }
                    ],
                    'TTL': 300
                }
            }
        ]
    }

    print("Updating Route53 to create:")
    print("{0}.private.{1}. IN A {2}".format(instance_name, HOSTED_PUB_ZONE_NAME, instance_ip))
    print("{0}.{1}. IN A {2}".format(instance_name, HOSTED_PRIV_ZONE_NAME, instance_ip))
    print("{0} IN PTR {1}.{2}.".format(instance_ip_rev, instance_name, HOSTED_PRIV_ZONE_NAME))

    if instance_ip_pub:
        
        if not instance_pub_name:
            instance_pub_name = instance_name

        dns_changes_pub = {
            'Changes': [
                {
                    'Action': 'UPSERT',
                    'ResourceRecordSet': {
                        'Name': "{0}.{1}.".format(instance_pub_name, HOSTED_PUB_ZONE_NAME),
                        'Type': 'A',
                        'ResourceRecords': [
                            {
                                'Value': instance_ip_pub
                            }
                        ],
                        'TTL': 300
                    }
                }
            ]
        }

        print("{0}.{1}. IN A {2}".format(instance_pub_name, HOSTED_PUB_ZONE_NAME, instance_ip_pub))

    response_pub_priv = route53.change_resource_record_sets(
        HostedZoneId=HOSTED_PUB_ZONE_ID,
        ChangeBatch=dns_changes_priv_pub
    )

    response_priv = route53.change_resource_record_sets(
        HostedZoneId=HOSTED_PRIV_ZONE_ID,
        ChangeBatch=dns_changes_priv
    )

    response_rev = route53.change_resource_record_sets(
        HostedZoneId=HOSTED_REV_PRIV_ZONE_ID,
        ChangeBatch=dns_changes_priv_rev
    )

    response_pub = route53.change_resource_record_sets(
        HostedZoneId=HOSTED_PUB_ZONE_ID,
        ChangeBatch=dns_changes_pub
    )

    return {'status_pub_prv':response_pub_priv['ChangeInfo']['Status'], 'status_priv':response_priv['ChangeInfo']['Status'], 'status_rev':response_rev['ChangeInfo']['Status'], 'status_pub':response_pub['ChangeInfo']['Status']}
