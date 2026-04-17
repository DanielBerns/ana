I am using python to develop a little script. I want to read a yaml nested configuration file.
Give me a script for reading a yaml file and print the content in screen
Use the following content

```yaml
# Configuration File
actions:
  - name: alpha
    cron: '0 0 * * *'  
    parameters: 
      path: ~/alpha
      var_0: 0
      var_1: 1
  - name: bravo
    cron: '0 1 * * *'  
    parameters: 
      path: ~/bravo
      var_2: 2
      var_3: 3
```yaml      
    
Give me a function to write a 
{"actions"}
