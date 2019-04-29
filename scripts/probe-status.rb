#!ruby
# issue M119 commands to smoothie

$stdout.sync = true

def send
    STDOUT.write("M119\n")
    while true
      l= STDIN.gets # read a line
      if l.start_with?("ok")
        return
      elsif l =~ /ERROR|ALARM|Error|HALT|error:Alarm|!!/
        exit 0
      else
        STDERR.write("#{l}\n")
      end
    end
end

while true
  send
  sleep(1)
end

