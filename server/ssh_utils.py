import boto3
import paramiko
ec2 = boto3.resource('ec2', region_name='us-east-1')

def create_instances(image_id, instance_type, security_group, key_name, num_instances):
    global ec2
    instances = ec2.create_instances(ImageId=image_id, InstanceType=instance_type,
                                     SecurityGroups=security_group, KeyName=key_name, MinCount=1,
                                     MaxCount=num_instances, TagSpecifications=[
                                         {
                                             'ResourceType': 'instance',
                                             'Tags': [
                                                 {
                                                     'Key': 'instance-type',
                                                     'Value': 'compute-node'
                                                 }
                                             ]
                                         }
                                     ])
    for instance in instances:
        instance.wait_until_running()
        # see this: https://stackoverflow.com/questions/52466933/public-ip-address-of-ec2-instance-is-none-while-the-instance-is-initializing
        instance.reload()
        print(instance.public_ip_address)

    return instances

def write_cluster_ip_conf(cluster_ip_conf_path, instances, port=5000):
    file = open(cluster_ip_conf_path, 'w')
    file.write('\nHeader add Set-Cookie "ROUTEID=.%{BALANCER_WORKER_ROUTE}e; path=/" env=BALANCER_ROUTE_CHANGED')
    file.write('\n<Proxy balancer://mycluster>')
    count = 0
    for instance in instances:
        count = count + 1
        file.write('\n\t# server {0}\n\
        BalancerMember http://{1}:{2}'.format(count, instance['public_ip_address'], port))
    file.write('\nProxySet stickysession=ROUTEID')    
    file.write('\n</Proxy>')
    file.close()

def serialize(channel):
    channel = channel.readlines()
    output = ""
    for line in channel:
        output = output + line
    return output

def exec_shell_command(ip_add, cfg, cmd):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(hostname=ip_add, username='ubuntu',
                key_filename=cfg.ec2_cluster_cfg['key_pair_path'])
    shell = ssh.invoke_shell()
    if shell.active:
        print('ssh_session is active, running command {0} \n on host {1}'.format(cmd, ip_add))
        # note: if container is already running, the command below will return exit_status = 1, because the port will have
        # already been allocated by the running container
        _, stdout, stderr = ssh.exec_command(cmd)
        print('stdout: {}'.format(serialize(stdout)))
        print('stderr: {}'.format(serialize(stderr)))
        print('******** closing shell **********')
        shell.close()
        ssh.close()
        return 0

    ssh.close()
    return -1
