#!ruby
# issue probe commands to smoothie
require 'optparse'
require 'ostruct'

class Optparse
    def self.parse(args)
        options = OpenStruct.new
        options.verbose = false
        options.job= 'size'
        options.width= 3*25.4;
        options.length= 2*25.4;
        options.z= 10;
        options.tool_dia= 4
        options.feed_rate=  1200 # mm/min
        options.diameter= 50
        options.points= 50
        options.test= false
        options.auto= false

        opt_parser= OptionParser.new do |opts|
          opts.banner = "Usage: probe.rb [options]"

          opts.on("-v", "--[no-]verbose", "Run verbosely") do |v|
            options.verbose = v
          end

          opts.on( "-j", "--job TYPE", String,
                   "The job to run one of [size|center|spiral|align|angle|pos]" ) do |n|
            options.job= n
          end

         opts.on( "-w", "--width WIDTH", Float,
                   "The width of the object being probed (#{options.width})" ) do |n|
            options.width= n
          end

         opts.on( "-l", "--length LENGTH", Float,
                   "The length of the object being probed (#{options.length})" ) do |n|
            options.length= n
          end

         opts.on( "-d", "--diameter DIAMETER", Float,
                   "The approx diameter of the hole being probed (#{options.diameter})" ) do |n|
            options.diameter= n
          end

          opts.on( "-z", "--safe-height Z", Float,
                   "Safe Height to move to above object (#{options.z})" ) do |opt|
            options.z= opt
          end

          opts.on( "-t", "--tool-diameter DIA", Float,
                   "diameter of tool (#{options.tool_dia})" ) do |opt|
              options.tool_dia= opt
          end

          opts.on( "-f", "--feed-rate FR", Float,
                   "feed rate to use" ) do |opt|
              options.feed_rate= opt
          end

          opts.on( "-n", "--points N", Float,
                   "number of points in spiral test" ) do |opt|
              options.points= opt
          end

          opts.on( "-x", "--[no-]test", "run as a test" ) do |opt|
              options.test= opt
          end

          opts.on( "-a", "--[no-]auto", "run auto if required" ) do |opt|
              options.auto= opt
          end

        end
        opt_parser.parse!(ARGV)
        options
    end
end

$options = Optparse.parse(ARGV)
@verbose= $options.verbose
$stdout.sync = true

# read from the port until we get the [PRB:1.000,80.137,10.000:0] response
def readPRB
    prb= OpenStruct.new
    prb.ok= false
    l= STDIN.gets # read a line
    STDERR.puts "DEBUG: #{l}" if @verbose
    # [PRB:1.000,80.137,10.000:0]
    if l.start_with?("[PRB:")
        a= l.split(':')
        if a[2][0] == '1'
            c= a[1].split(',')
            prb.ok= true
            prb.x= c[0].to_f
            prb.y= c[1].to_f
            prb.z= c[2].to_f
        end
    else
      raise "unexpected response to probe: #{l}"
    end

    # read the ok
    l= STDIN.gets # read a line
    STDERR.puts "DEBUG: #{l}" if @verbose
    if !l.start_with?("ok")
      raise "unexpected response after probe: #{l}"
    end

    prb
end

# send query to get current position
def getpos(mpos=false)
  STDOUT.write("?")
  l= STDIN.gets # read a line
  STDERR.puts "DEBUG: #{l}" if @verbose
  # <Idle|MPos:3.3637,2.1275,0.0000|WPos:-0.0175,2.1275,0.0000|F:1800.0,100.0>
  if l.start_with?("<")
    if mpos
      m= l.match(/MPos:([-0-9.]+),([-0-9.]+),([-0-9.]+)/)
    else
      m= l.match(/WPos:([-0-9.]+),([-0-9.]+),([-0-9.]+)/)
    end
    unless m.nil?
      pos= OpenStruct.new
      pos.x, pos.y, pos.z = m[1..3].collect{ |i| i.to_f }
      return pos
    end
  end

  raise "unexpected response after query: #{l}"
end

def send(arg, wait=true)
    STDERR.puts "DEBUG: sending #{arg}" if @verbose
    STDOUT.write(arg + "\n")
    if wait and !$options.test
      # wait for ok
      l= STDIN.gets # read a line
      STDERR.puts "DEBUG: #{l}" if @verbose
      if !l.start_with?("ok")
        raise "unexpected response to #{arg}: #{l}"
      end
    end
end

def wait
    # wait for all moves to finish
    send('M400')
end

def send_expect(arg, expect, wait=true)
    STDERR.puts "DEBUG: sending #{arg}" if @verbose
    STDOUT.write(arg + "\n")
    if expect and !$options.test
      # wait for expect
      l= STDIN.gets # read a line
      STDERR.puts "DEBUG: #{l}" if @verbose
      if l.match(expect).nil?
        raise "unexpected response: #{l}"
      end
    end

    if wait and !$options.test
      # wait for ok
      l= STDIN.gets # read a line
      STDERR.puts "DEBUG: #{l}" if @verbose
      if !l.start_with?("ok")
        raise "unexpected response: #{l}"
      end
    end

end

def moveBy(x: 0, y: 0, z: 0, down: true, up: true)
    send("G91 G0 Z#{$options.z}") if up
    send("G91 G0 X#{x} Y#{y} Z#{z}")
    send("G0 Z#{-$options.z}") if down
    send("G90")
end

def moveTo(x: nil, y: nil, z: nil, down: true, up: true)
    send("G91 G0 Z#{$options.z}") if up
    args= ""
    args += "X#{x} " unless x.nil?
    args += "Y#{y} " unless y.nil?
    args += "Z#{z} " unless z.nil?
    send("G90 G0 #{args}")
    send("G91 G0 Z#{-$options.z}") if down
    send("G90")
end

def probe(axis, amount)
    send("G38.3 #{axis.to_s.upcase}#{amount}", false)
    r= readPRB
    STDERR.puts "DEBUG: got: #{r}" if $verbose
    raise "Probe failed" unless r.ok
    r
end

def probe_size

    STDERR.puts "Position tool about 10mm to the left of the object to measure"
    d1= $options.tool_dia
    d2= $options.tool_dia/2.0

    r1= probe(:x, 20)

    moveBy(x: $options.width+10)

    r2= probe(:x, -20) # probe left

    width= r2.x - r1.x - d1
    STDERR.puts "Width= #{width}, expected= #{$options.width}, difference= #{$options.width-width}"

    # center in X and in front of Y face
    moveBy(x: -width/2.0-d2, y: -$options.length/2.0-10)

    r1= probe(:y, 20)

    moveBy(y: $options.length+10)

    r2= probe(:y, -20) # probe negative Y

    length= r2.y - r1.y - d1
    STDERR.puts "Length= #{length}, expected= #{$options.length}, difference= #{$options.length-length}"

    # center in Y
    moveBy(y: -length/2.0-d2, down: false)

    STDERR.puts "Size= #{length} x #{width}"
end

def probe_center
    STDERR.puts "Position tool approx in the center of the hole"
    d1= $options.tool_dia
    # get current position
    wp= getpos()

    r1= probe(:x, $options.diameter+20) # probe right
    moveTo(x: wp.x, up: false, down: false) # move back to start

    r2= probe(:x, -($options.diameter+20)) # probe left

    diam= r1.x - r2.x
    # center in X
    moveBy(x: diam/2.0, up: false, down: false)

    r1= probe(:y, $options.diameter+20) # probe back
    moveBy(y: wp.y, up: false, down: false) # to speed things up a bit get back to approx center
    r2= probe(:y, -($options.diameter+20)) # probe front

    diam= r1.y - r2.y

    # center in Y
    moveBy(y: diam/2.0, up: false, down: false)

    STDERR.puts "Diameter is #{diam+d1} mm"
end

def probe_spiral(n, radius)
    a = radius / (2.0 * Math::sqrt(n * Math::PI))
    step_length = radius * radius / (2 * a * n)

    maxz = -1e6
    minz = 1e6
    zs = $options.z
    (0..n).each do |i|
        angle = Math::sqrt(2 * (i * step_length) / a)
        r = angle * a
        # polar to cartesian
        x = r * Math::cos(angle)
        y = r * Math::sin(angle)
        moveTo(x: x, y: y, z: zs, up: false, down: false)
        p1 = probe(:z, -20)
        z= p1.z
        moveTo(z: zs, up: false, down: false)
        STDERR.puts("PROBE: X#{x}, Y#{y}, Z#{z}")
        maxz = z if(z > maxz)
        minz = z if(z < minz)
    end

    STDERR.puts("max: #{maxz}, min: #{minz}, delta: #{maxz-minz}")
end

def probe_align_y

    STDERR.puts "Position probe at far right of edge to probe"
    w = $options.width

    # find initial position
    probe(:y, 20)
    moveBy(y: -5, up: false, down: false) # move off 5mm

    # probe again
    r1= probe(:y, 20)
    moveBy(y: -5, up: false, down: false) # move off 5mm
    moveBy(x: -w, up: false, down: false) # move to left 500mm
    r2= probe(:y, 20)

    diff= r2.y - r1.y
    STDERR.puts "#{r1.y} - #{r2.y}: Y is out of alignment by #{diff.abs} mm"

    spmm= get_steps_mm
    steps= diff.abs * spmm.y

    if diff < 0
        STDERR.puts "Right hand actuator needs to be moved in +Y direction by about #{steps} steps"
    else
        STDERR.puts "Right hand actuator needs to be moved in -Y direction by about #{steps} steps"
        steps= -steps
    end

    if $options.auto
        STDERR.puts "Adjusting right Y motor by #{steps}"
        send("test raw a #{steps} 100")
    end

    # return to start position
    moveBy(y: -10, up: false, down: false)
    moveBy(x: w, up: false, down: false)

end

# send query to get current angle
def get_angle()
  STDOUT.write "M114.3\n"
  l= STDIN.gets # read a line
  STDERR.puts "DEBUG: #{l}" if @verbose
  # ok APOS: X:-16.4493 Y:-16.4493 Z:-16.4493
  if l.start_with?("ok APOS: ")
      m= l.match(/.*X:([-0-9.]+) Y:([-0-9.]+) Z:([-0-9.]+)/)
    unless m.nil?
      pos= OpenStruct.new
      pos.x, pos.y, pos.z = m[1..3].collect{ |i| i.to_f }
      return pos
    end
  end

  raise "unexpected response after M114.3: #{l}"
end

# send query to get current steps/mm
def get_steps_mm()
  STDOUT.write "M92\n"
  l= STDIN.gets # read a line
  STDERR.puts "DEBUG: #{l}" if @verbose
  # X:1600.000000 Y:1600.000000 Z:1600.000000\nok

  if l.start_with?("X:")
      m= l.match(/X:([-0-9.]+) Y:([-0-9.]+) Z:([-0-9.]+)/)
    unless m.nil?
      pos= OpenStruct.new
      pos.x, pos.y, pos.z = m[1..3].collect{ |i| i.to_f }

      # wait for ok
      l= STDIN.gets # read a line
      STDERR.puts "DEBUG: #{l}" if @verbose
      if !l.start_with?("ok")
        raise "unexpected response to M92: #{l}"
      end

      return pos
    end
  end

  raise "unexpected response after query: #{l}"
end

# Special tool for rotary delta, measures the movement between two known points to calculate a known angle
def probe_angle()
    moveTo(x: 0, y: 0, z: 90, up: false, down: false)
    send_expect "G30.1", "Z:"
    a1 = get_angle.x

    moveBy z: 1, up: false, down: false

    send_expect "G30.1 R1", "Z:"
    a2 = get_angle.x

    d= (a2-a1).abs
    if d == 0
      ds= 1.0
    else
      ds= d / 27.917376257801326
    end

    STDERR.puts("a1: #{a1}, a2: #{a2}, delta: #{d}, ds: #{ds}")
    # current steps/degree * ds = new steps/degree
    spmm = get_steps_mm
    nspmm = spmm.x * ds
    STDERR.puts("Old #{spmm.x}, New: #{nspmm}")
    STDERR.puts("M92 X#{nspmm} Y#{nspmm} Z#{nspmm}")
end

# first send blank line and wait for 'ok' as there maybe some queued up stuff which we need to ignore
if !$options.test
    STDOUT.write("\n")
    while true
        l= STDIN.gets # read a line
        break if l.start_with?("ok")
    end
end

if $options.job == 'size'
begin
  send("M120")
  probe_size
  wait
ensure
  send("M121")
end

elsif $options.job == 'center'
begin
  send("M120")
  probe_center
  wait
ensure
  send("M121")
end

elsif $options.job == 'spiral'
begin
  send("M120")
  probe_spiral($options.points, $options.diameter/2.0)
  wait
ensure
  send("M121")
end

elsif $options.job == 'pos'
wp= getpos()
mp = getpos(true)
STDERR.puts "WPOS x#{wp.x} y#{wp.y} z#{wp.z} MPOS x#{mp.x} y#{mp.y} z#{mp.z}"

elsif $options.job == 'angle'
probe_angle
wait

elsif $options.job == 'align'
probe_align_y
wait

else
  STDERR.puts "job #{$options.job} Not yet supported"
  exit 1
end

exit 0
