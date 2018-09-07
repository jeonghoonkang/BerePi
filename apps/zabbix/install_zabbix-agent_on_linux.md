# Installing Zabbix agent on Linux



## 1. Download

  - [Link](http://repo.zabbix.com/zabbix/3.4/ubuntu/pool/main/z/zabbix/): Download the zabbix-agent for OS version
  - ex) zabbix agent 3.4.9 Ubuntu 14.04 LTS 64bit

  ```Shell
  $ mkdir ~/zabbix_bin
  $ mkdir ~/zabbix_bin/zabbix_agent
  $ cd ~/zabbix_bin/zabbix_agent
  $ wget http://repo.zabbix.com/zabbix/3.4/ubuntu/pool/main/z/zabbix/zabbix-agent_3.4.9-1%2Btrusty_amd64.deb
  ```

## 2. Install

   - required for libc6 (2.17) or later

   ```Shell
   $ sudo dpkg -i zabbix-agent_3.4.9-1+trusty_amd64.deb
   ```

## 3. Configuration

   1) copy zabbix-agentd.conf file

   ```Shell
   $ sudo cp /etc/zabbix/zabbix-agentd.conf /etc/zabbix/zabbix-agentd.conf.bak
   $ sudo cp BerePi/apps/zabbix/conf/zabbix_agentd.rpi2.conf /etc/zabbix/zabbix-agentd.conf
   ```

   2) Edit zabbix-agentd.conf

   ```Shell
   $ sudo vi /etc/zabbix/zabbix_agentd.conf
   ```


   ```conf
   Hostname=<Your hostname>
   ```

   3) Enable system service

   ```Shell
   $ sudo systemctl enable zabbix-agent.service
   ```
   
   4) Restart zabbix-agent
   
   ```Shell
   $ sudo systemctl restart zabbix-agent.service
   ```


## 4. Configuring a host

### 1) Configuration > Hosts > Create host

      - Host name : <Your name>
      - Groups : select host groups
      - Agent interfaces
          - Public IP : IP/DNS
          - Private IP/Active mode : 0.0.0.0

### 2) Templates : line templates

     - 'Select'
     - 'Template OS Linux Active'

### 3) Monitoring > Graphs : Check to receiving data

## 5. Appendixes

### 1) Zabbix agent TEST

```Shell
$ sudo /etc/init.d/zabbix-agent status

$ zabbix_agentd -t user.proc.allcpu[<process>]
```

[Link](http://www.zabbix.com/download.php)
