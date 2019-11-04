import boto3
import os
import time
import config_ec2_cluster as cfg
from ssh_utils import exec_shell_command, create_instances, write_cluster_ip_conf

session = boto3.Session(profile_name='ankur-eks-dev')
ec2 = boto3.resource('ec2', region_name='us-east-1')
ec2_client = boto3.client('ec2', region_name='us-east-1')

num_instances = cfg.ec2_cluster_cfg['num_instances']

# cmd to run
login_github = 'docker login docker.pkg.github.com -u ' + cfg.github_cfg['user_name'] + ' ' + '-p ' + \
               cfg.github_cfg['token']
pull_container = 'docker pull ' + cfg.ec2_cluster_cfg['container_name']
stop_container = 'docker stop $(docker ps -a -q)'
prune_container = 'docker system prune -f'
run_container = 'docker container run -t -i -d -p 5000:5000 ' + '--env "MY_IPS=$(hostname)" ' + cfg.ec2_cluster_cfg['container_name']
cmd = login_github + ';' + stop_container + ';' + prune_container + ';' + pull_container + ';' + run_container

# check if a EC2 instances is already running, if not create an instance
running_instances = ec2.instances.filter(
    Filters=[{'Name': 'instance-state-name', 'Values': ['running']}, {'Name': 'instance-type', 'Values': ['t2.micro']}])
# create list of instances
running_instance_list = [instance for instance in running_instances]
num_running_instances = len(running_instance_list)

if num_running_instances >= num_instances: # we have enough running instances, we can run the container
    for instance in running_instances:
        exec_shell_command(instance.public_ip_address, cfg, cmd)
else:
    num_instances_needed = num_instances - num_running_instances
    # if we don't have enough running instances, check if there are any stopped instances
    stopped_instances = ec2.instances.filter(
        Filters=[{'Name': 'instance-state-name', 'Values': ['stopped']}, {'Name': 'instance-type', 'Values': ['t2.micro']}])
    # create list of instances
    stopped_instance_list = [instance for instance in stopped_instances]
    stopped_instance_ids = [instance.id for instance in stopped_instances]
    num_stopped_instances = len(stopped_instance_list)
    stopped_instance_ids = stopped_instance_ids[0:min(num_stopped_instances, num_instances_needed)]
    # start the stopped instances and add to running instances list
    ec2_client.start_instances(InstanceIds=stopped_instance_ids)
    # checking for instance_status_ok is more reliable than instance_ready
    # because the instance is sure to be ready. If we only wait for instance_ready
    # ssh can sometimes fail. 
    waiter = ec2_client.get_waiter('instance_status_ok')
    waiter.wait(InstanceIds=stopped_instance_ids, WaiterConfig={
        'Delay': 5,
        'MaxAttempts': 1000
    })
    # now all instances should be running
    running_instances = ec2.instances.filter(
        Filters=[{'Name': 'instance-state-name', 'Values': ['running']},
                 {'Name': 'instance-type', 'Values': ['t2.micro']}])
    # create list of instances
    running_instance_list = [instance for instance in running_instances]
    num_running_instances = len(running_instance_list)

    num_running_instances = len(running_instance_list)
    if num_running_instances >= num_instances: # we have enough running instances, we can run the container
        for instance in running_instances:
            exec_shell_command(instance.public_ip_address, cfg, cmd)

    # otherwise, create new instances and run command
    else:
        instances = create_instances(cfg.ec2_cluster_cfg['ami_id'], cfg.ec2_cluster_cfg['instance_type'], \
                                     [cfg.ec2_cluster_cfg['sec_grp']], cfg.ec2_cluster_cfg['key_pair'], num_instances - num_running_instances )
        # print properties
        for instance in instances:
            print(instance.id, instance.instance_type, instance.public_ip_address)
            running_instance_list.append(instance)
        # at this point number of running instances must be equal to number of instances needed in our cluster
        num_running_instances = len(running_instance_list)
        # verify num_running_instances == num_instances
        for instance in running_instances:
            exec_shell_command(instance.public_ip_address, cfg, cmd)

# at this point we should have as many running instances as we need
# create cluster-ip.conf with the new IPs
# should look like this:
"""
<Proxy balancer://mycluster>
    #server 1
    BalancerMember ip_address
    # server 2..
</Proxy>    
"""
if num_running_instances >= num_instances:
    print("writing instances ip to cluster config (cluster_ip.conf)")
    write_cluster_ip_conf(cfg.ec2_cluster_cfg['cluster_ip_conf_path'], running_instances)
    print("restarting apache proxy")
    stream = os.popen('sudo ./../proxy-apache-conf/ctlscript.sh restart apache')
    output = stream.read()
    print(output)
    

print('done')




