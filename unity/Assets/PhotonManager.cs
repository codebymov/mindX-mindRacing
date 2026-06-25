using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using Photon.Pun;
using Photon.Realtime;

public class PhotonManager : MonoBehaviourPunCallbacks
{
    // Called when the script instance is being loaded
    void Start()
    {
        Debug.Log("Connecting to Photon...");
        PhotonNetwork.ConnectUsingSettings();
    }

    // Callback: Called when the client is connected to the master server
    public override void OnConnectedToMaster()
    {
        Debug.Log("Connected to Master. Joining Lobby...");
        PhotonNetwork.JoinLobby();
    }

    // Callback: Called when the client is connected to a lobby
    public override void OnJoinedLobby()
    {
        Debug.Log("Joined Lobby.");
        // Optionally, create or join a room here
        CreateRoom(); // Or JoinRoom("RoomName") as required.
    }

    // Function to create a room
    public void CreateRoom()
    {
        string roomName = "Room_" + Random.Range(0, 10000);
        RoomOptions roomOptions = new RoomOptions();
        roomOptions.MaxPlayers = 2;

        Debug.Log("Creating Room: " + roomName);
        PhotonNetwork.CreateRoom(roomName, roomOptions, TypedLobby.Default);
    }

    // Callback: Called when the client has just created a room
    public override void OnCreatedRoom()
    {
        Debug.Log("Room Created Successfully.");
    }

    // Callback: Called when the client joins a room
    public override void OnJoinedRoom()
    {
        Debug.Log("Joined Room: " + PhotonNetwork.CurrentRoom.Name);
    }

    // Callback: Called when the client failed to create a room
    public override void OnCreateRoomFailed(short returnCode, string message)
    {
        Debug.LogError("Failed to Create Room: " + message);
    }

    // Function to handle joining a specific room
    public void JoinRoom(string roomName)
    {
        Debug.Log("Joining Room: " + roomName);
        PhotonNetwork.JoinRoom(roomName);
    }

    // Callback: Called when the client failed to join a room
    public override void OnJoinRoomFailed(short returnCode, string message)
    {
        Debug.LogError("Failed to Join Room: " + message);
    }

    // Callback: Called when another player joins the room
    public override void OnPlayerEnteredRoom(Player newPlayer)
    {
        Debug.Log("Player Entered Room: " + newPlayer.NickName);
    }

    // Callback: Called when another player leaves the room
    public override void OnPlayerLeftRoom(Player otherPlayer)
    {
        Debug.Log("Player Left Room: " + otherPlayer.NickName);
    }
}
