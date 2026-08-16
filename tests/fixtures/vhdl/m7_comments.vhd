-- context header must remain unassociated
library ieee; -- library context must not attach to the entity
-- context import must remain unassociated
use ieee.std_logic_1164.all;

--! Commented datapath
entity M7Comments is
    port (
        -- source port
        source          : in  std_logic; -- sampled input
        assigned_result : out std_logic;
        process_result  : out std_logic
    );
end entity M7Comments;

-- architecture heading must remain unassociated
architecture rtl of M7Comments is
    -- intermediate signal
    signal internal_value : std_logic;
begin
    -- internal connection
    internal_value <= source;

    -- concurrent output
    assigned_result <= internal_value;

    -- combinational output process
    comb_logic : process (source)
    begin
        -- process assignment
        process_result <= source;
    end process;
end architecture rtl;
