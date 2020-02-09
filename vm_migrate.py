#!/usr/bin/python

import libvirt
from xml.dom import minidom
from time import sleep
from subprocess import Popen,PIPE

DST_USER = 'root'
DST_PORT = '22'
DST_HOST='172.20.30.45'
DST_KEYFILE = '/root/.ssh/id_rsa'
DST_STORAGE_PATH = '/var/lib/libvirt/images'

def ConnectToQEMU(remote=False,user="root",host="192.168.0.1",port=22,keyfile="~/.ssh/id_rsa"):
	try:
		if(remote == False):
			return libvirt.open("qemu:///system")
		else:
			return libvirt.open("qemu+ssh://{}@{}:{}/system?keyfile={}".format(user,host,port,keyfile))
	except:
		return None

def run_cmd(cmd):
    #print(cmd)
	p = Popen(cmd,shell=True,stdout=PIPE,stderr=PIPE)
	stdout,stderr =  p.communicate()
	return stdout.decode('utf-8'), stderr.decode('utf-8')

def ListVMdomains(src_conn):
	listd = src_conn.listDomainsID()
	listd.sort()

	print("""---------------------------------------------------
	ANO KVM QEMU VM Migration system
		Virtual Machines list
--------------------------------------------------- 
		""")
	if(listd):
		print('	ID: 0  -- To Migration all the machines \n\n')
		for i in listd:
			d = src_conn.lookupByID(i)
			print(" VM ID:{} -- VM Name:{}".format(i,d.name()))
		print("---------------------------------------------------\n\n")

		vmid = int(input('VM ID: '))
		if(vmid != 0):
			return (vmid,)
		return listd
	return None

def ExportVM(src_conn,vmid):
	Disks = []
	if(vmid != 0):
		vm = src_conn.lookupByID(vmid)
		vm_name = vm.name()

		## Prin 
		print("Export VM {} DomXML".format(vm_name))

		## find drive configuration from source server
		if(vm.isActive()):
			raw_xml = vm.XMLDesc(0)
			xml = minidom.parseString(raw_xml)
			diskTypes = xml.getElementsByTagName('disk')
			for diskType in diskTypes:
				if(diskType.getAttribute('device') == 'disk'):
					DiskXML = {}
					DiskXML[diskType.getAttribute('device')] = {}
					diskNodes = diskType.childNodes
					for diskNode in diskNodes:
						if diskNode.nodeName[0:1] != '#':
							DiskXML[diskType.getAttribute('device')][diskNode.nodeName] = {}
							for attr in diskNode.attributes.keys():
								DiskXML[diskType.getAttribute('device')][diskNode.nodeName][diskNode.attributes[attr].name] = diskNode.attributes[attr].value
					Disks.append(DiskXML)

			## change disk storage location
			xmldom = raw_xml
			for i in Disks:
				disk_path = i['disk']['source']['file']
				disk_arr = disk_path.split('/')
				xmldom = xmldom.replace(disk_path,'{}/{}'.format(DST_STORAGE_PATH,disk_arr[-1]))
	return Disks,xmldom

def ImportVM(conn,data,domxml):
	for i in data:
		rsync = 'rsync -avP -e"ssh -p {PORT} -i {KEY}" {SRC_PATH} {USER}@{HOST}:{DST_PATH}'.format(
			PORT=DST_PORT,
			HOST=DST_HOST,
			KEY=DST_KEYFILE,
			USER=DST_USER,
			SRC_PATH=i['disk']['source']['file'],
			DST_PATH=DST_STORAGE_PATH+'/'
		)
		dimg = i['disk']['source']['file'].split('/')
		print("Copying disk image: {}".format(dimg[-1]))
		stdout,stderr = run_cmd(rsync)
		if(stderr):
			print('ERROR Unable to copy the disk image: {}'.fomrat(stderr))
			exit(1)
		print('------------------ rsync result for img: {}: ------------------'.format(dimg[-1]))
		print(stdout)
	### importing DomXML
	print('Importing DomXML to host: {}'.format(DST_HOST))
	dom = conn.defineXML(domxml)
	dom.create()

def main():
	src_conn = ConnectToQEMU(remote=False)
	dst_conn = ConnectToQEMU(remote=True,user=DST_USER,host=DST_HOST,port=DST_PORT,keyfile=DST_KEYFILE)
	
	vmids = ListVMdomains(src_conn)
	
	if(vmids):
		for vmid in vmids:
			vm = src_conn.lookupByID(vmid)
			print('-------------- Start migration for VM: {} --------------'.format(vm.name()))
			Disks,domxml = ExportVM(src_conn,vmid)
			print("Shutting down VM {}".format(vm.name()))
			vm.shutdown()
			while True:
				if(not vm.isActive()):
					ImportVM(dst_conn,Disks,domxml)
					break
				sleep(1)
			print('-------------- End migration for VM: {} --------------\n\n'.format(vm.name()))
	else:
		print('No VMs to migrate')

	src_conn.close()
	dst_conn.close()

main()