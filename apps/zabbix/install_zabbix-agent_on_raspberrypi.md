# Installing Zabbix agent on raspberry pi



## 1. Download

  ```Shell
  $ wget https://github.com/ipmstyle/zabbix_on_raspberry_pi/raw/master/zabbix-agent_3.4.12-1%2Bstretch_armhf.deb
  ```

## 2. Install

   ```Shell
   $ sudo dpkg -i zabbix-agent_3.4.12-1+stretch_armhf.deb
   ```

## 3. Configuration

### 1) copy zabbix-agentd.conf file

   ```Shell
   $ sudo cp /etc/zabbix/zabbix-agentd.conf /etc/zabbix/zabbix-agentd.conf.bak
   $ sudo cp BerePi/apps/zabbix/conf/zabbix_agentd.rpi2.conf /etc/zabbix/zabbix-agentd.conf
   ```

### 2) Edit zabbix-agentd.conf

   ```Shell
   $ sudo vi /etc/zabbix/zabbix_agentd.conf
   ```

   ```conf
   Hostname=<hostname>
   ```

### 3) Enable system service

  ```Shell
  $ sudo systemctl enable zabbix-agent.service
  ```

### 4) Restart zabbix-agent

   ```Shell
   $ sudo systemctl restart zabbix-agent.service
   ```


## 4. Configuring a host

### 1) Configuration > Hosts > Create host

     - Host name : \<Your name>
     - Groups : select host groups
     - Agent interfaces
       - Public IP : IP/DNS
       - Private IP/Active mode : 0.0.0.0

### 2) Templates : link templates

     - 'Select'
     - 'Template OS Linux Active', 'Template App STALK Service Active', 'Template App Raspberry Pi Active'

### 3) Monitoring > Graphs : Check to receiving data

## 5. Appendixes

### 1) Zabbix agent TEST

```Shell
$ sudo /etc/init.d/zabbix-agent status

$ zabbix_agentd -t user.proc.allcpu[<process>]
```

[Link](http://www.zabbix.com/download.php)
