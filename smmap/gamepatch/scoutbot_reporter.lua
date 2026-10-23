-- >>> SCOUTBOT REPORTER v1 >>>
-- Added by Scoutbot so its map can show where you are. It only prints your
-- position to the game log. Stop in Scoutbot (or
-- `python -m smmap.gamepatch --unpatch`) removes it and leaves this file as
-- Steam installed it.
do
	-- The game steps 40 fixed ticks a second; one report every 4 is 10 a second.
	local SCOUTBOT_EVERY = 4
	local scoutbotBase = SurvivalPlayer.client_onFixedUpdate
	local scoutbotFailed = false

	local function scoutbotReport( self )
		local player = sm.localPlayer.getPlayer()
		if self.player ~= player then
			return
		end
		local tick = sm.game.getCurrentTick()
		if tick % SCOUTBOT_EVERY ~= 0 then
			return
		end
		local character = player.character
		if character == nil or not sm.exists( character ) then
			return
		end
		local p = character.worldPosition
		local d = character.direction
		local world = character:getWorld()
		sm.log.info( string.format(
			'[SMMAP]{"x":%.3f,"y":%.3f,"z":%.3f,"yaw":%.4f,"world":%d,"t":%d}',
			p.x, p.y, p.z, math.atan2( d.y, d.x ), world and world.id or -1, tick ) )
	end

	-- Wraps the player's own fixed update rather than editing it, so the only
	-- change to the game's code is this block at the end of the file. A
	-- failing report is logged once and never stops the game's update.
	function SurvivalPlayer.client_onFixedUpdate( self, dt )
		scoutbotBase( self, dt )
		local ok, err = pcall( scoutbotReport, self )
		if not ok and not scoutbotFailed then
			scoutbotFailed = true
			sm.log.warning( "[SMMAP-ERROR]" .. tostring( err ) )
		end
	end
end
-- <<< SCOUTBOT REPORTER <<<
