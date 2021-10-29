-- bump 56.0.2924.84-2017-07-20
gl.setup(NATIVE_WIDTH, NATIVE_HEIGHT)

local logo = resource.load_image "logo.png"

local alpha = 1
local fade = false

util.data_mapper{
    fade = function()
        fade = true
    end
}

function node.render()
    if fade then
        alpha = alpha - 0.01
    end
    if alpha < 0 then
        logo:dispose()
        gl.clear(0, 0, 0, 0)
    else
        gl.clear(1, 1, 1, alpha)
        gl.translate(WIDTH/2, HEIGHT/2)
        gl.rotate(sys.now() * 30, 0, 0, 1)
        logo:draw(-60, -60, 60, 60, alpha)
    end
end
