#!/usr/bin/env python3
import os
import sys
import json
from pathlib import Path

# Ensure paths are configured
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from simulator.state_persistence import StateManager

def main():
    print("=======================================================================")
    print("🔄 DATABASE SYNCHRONIZATION PIPELINE")
    print("=======================================================================\n")
    
    # Instantiate state manager
    sm = StateManager(backend='postgres')
    
    if not sm.db_connected:
        print("❌ Error: Cannot connect to the remote database host.")
        print("Verify your DB_HOST IP address and check postgres authentication configs.")
        sys.exit(1)
        
    print("✓ Successfully connected to PostgreSQL database.\n")
    
    # 1. Sync Agent Parameters
    agent_path = Path("agent_parameters.json")
    if agent_path.exists():
        print("[1/2] Syncing agent parameters from agent_parameters.json...")
        try:
            with open(agent_path, 'r') as f:
                agent_data = json.load(f)
            
            for agent_name, params in agent_data.items():
                success = sm.save_agent_parameters(agent_name, params)
                if success:
                    print(f"  ✓ Synced parameters for agent: '{agent_name}'")
                else:
                    print(f"  ❌ Failed to sync parameters for agent: '{agent_name}'")
        except Exception as e:
            print(f"  ❌ Error reading local agent parameters: {e}")
    else:
        print("[-] agent_parameters.json not found locally. Skipping agent sync.")
        
    print()
    
    # 2. Sync Learner states (model parameters)
    model_path = Path("model_parameters.json")
    if model_path.exists():
        print("[2/2] Syncing model parameters from model_parameters.json...")
        try:
            with open(model_path, 'r') as f:
                model_data = json.load(f)
            
            for symbol, state_dict in model_data.items():
                success = sm.save_learner_state(symbol, state_dict)
                if success:
                    print(f"  ✓ Synced state calibration for symbol: '{symbol}'")
                else:
                    print(f"  ❌ Failed to sync state calibration for symbol: '{symbol}'")
        except Exception as e:
            print(f"  ❌ Error reading local model parameters: {e}")
    else:
        print("[-] model_parameters.json not found locally. Skipping model state sync.")
        
    print("\n=======================================================================")
    print("🎯 SYNCHRONIZATION PIPELINE FINISHED!")
    print("=======================================================================")

if __name__ == '__main__':
    main()
