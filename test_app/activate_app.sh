#!/bin/bash
# Wrapper script to activate the popup app via D-Bus
exec gdbus call --session --dest com.example.PopupApp --object-path /com/example/PopupApp --method com.example.PopupApp.Activate
