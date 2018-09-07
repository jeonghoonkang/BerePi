# Installing zabbix agent on Windows

## 1. Download

   * http://www.zabbix.com/download.php > Zabbix pre-compiled agents > Zabbix 3.4 > Windows download **or** [Driect download](https://www.zabbix.com/downloads/3.4.6/zabbix_agents_3.4.6.win.zip)
   * Unzip for C:\ drive

   ```diretory
.C:\
¦---- zabbix_agents_3.4.6.win
¦     ¦---- bin
¦     ¦    ¦---- win32
¦     ¦    ¦---- win64
¦     ¦---- conf
   ```

## 2. Configuration

### 1) Download

- zabbix-agentd.conf file : [Download](https://raw.githubusercontent.com/ipmstyle/zabbix_on_raspberry_pi/master/conf/zabbix_agentd.win.conf)
  
### 2) Edit zabbix-agentd.conf

   ```
LogFile=c:\zabbix_agents_3.4.6.win\zabbix_agentd.log
Server=118.129.98.184
ServerActive=118.129.98.184
Hostname=<Your Hostname>
   ```

## 3. Install

  * Win + x -> commadn Prompt(Admin)
  ```
  cd c:\zabbix_agents_3.4.6.win\bin\win64
  zabbix_agentd.exe --config c:\zabbix_agents_3.4.6.win\conf\zabbix_agentd.win.conf --install
  zabbix_agentd.exe --start
  ```

## 4. Configuring a host

### 1) Configuration > Hosts > Create host

   - Host name : <Your name>
   - Groups : slect host groups
   - Agent interfaces
        - Public IP : IP/DNS
        - Private IP/Active mode : 0.0.0.0

### 2) select Template

   - 'Select' > Template OS Windows Active'

### 3) Check to receiving data

   - Monitoring > Graphs


## 6. Appendixes

### 1) Portable zabbix-agent

   ```
   cd c:\zabbix_agents_3.4.6.win\bin\win64
   zabbix_agentd.exe -f --config c:\zabbix_agents_3.4.6.win\conf\zabbix_agentd.win.conf
   ```

### 2) Zabbix agent TEST

   ```Shell
   $ sudo /etc/init.d/zabbix-agent status
   $ zabbix_agentd -t user.proc.allcpu[<process>]
   ```
   
[http://www.zabbix.com/download.php](http://www.zabbix.com/download.php)
