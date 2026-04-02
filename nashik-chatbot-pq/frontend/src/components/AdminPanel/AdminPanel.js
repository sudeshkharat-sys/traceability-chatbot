import React, { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import adminService from "../../services/api/adminService";
import authService from "../../services/api/authService";
import "./AdminPanel.css";

const ROLES = ["admin", "user", "part_labeler"];

function AdminPanel() {
  const navigate = useNavigate();
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [actionMsg, setActionMsg] = useState("");
  const [confirmDelete, setConfirmDelete] = useState(null); // user_id pending delete
  const [roleChanging, setRoleChanging] = useState({}); // { user_id: true }

  const currentUserId = authService.getUserId();

  const loadUsers = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await adminService.getUsers();
      setUsers(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadUsers();
  }, [loadUsers]);

  const handleDeleteConfirm = async () => {
    if (!confirmDelete) return;
    try {
      await adminService.deleteUser(confirmDelete);
      setActionMsg("User deleted successfully.");
      setUsers((prev) => prev.filter((u) => u.user_id !== confirmDelete));
    } catch (e) {
      setError(e.message);
    } finally {
      setConfirmDelete(null);
    }
  };

  const handleRoleChange = async (userId, newRole) => {
    setRoleChanging((prev) => ({ ...prev, [userId]: true }));
    setError("");
    try {
      await adminService.updateRole(userId, newRole);
      setUsers((prev) =>
        prev.map((u) => (u.user_id === userId ? { ...u, role: newRole } : u))
      );
      setActionMsg(`Role updated to "${newRole}".`);
    } catch (e) {
      setError(e.message);
    } finally {
      setRoleChanging((prev) => ({ ...prev, [userId]: false }));
    }
  };

  const roleBadgeClass = (role) => {
    if (role === "admin") return "badge badge-admin";
    if (role === "part_labeler") return "badge badge-pl";
    return "badge badge-user";
  };

  return (
    <div className="admin-panel">
      {/* Header */}
      <div className="admin-header">
        <div className="admin-header-left">
          <button className="back-btn" onClick={() => navigate("/")}>
            ← Back
          </button>
          <h1 className="admin-title">Admin Panel</h1>
        </div>
        <span className="admin-subtitle">
          Logged in as <strong>{authService.getFullName()}</strong>
        </span>
      </div>

      {/* Status messages */}
      {error && (
        <div className="admin-alert admin-alert-error" onClick={() => setError("")}>
          {error} <span className="alert-close">✕</span>
        </div>
      )}
      {actionMsg && (
        <div className="admin-alert admin-alert-success" onClick={() => setActionMsg("")}>
          {actionMsg} <span className="alert-close">✕</span>
        </div>
      )}

      {/* Stats bar */}
      {!loading && (
        <div className="admin-stats">
          <div className="stat-chip">
            <span className="stat-num">{users.length}</span> Total Users
          </div>
          <div className="stat-chip">
            <span className="stat-num">{users.filter((u) => u.role === "admin").length}</span> Admins
          </div>
          <div className="stat-chip">
            <span className="stat-num">{users.filter((u) => u.role === "user").length}</span> Users
          </div>
          <div className="stat-chip">
            <span className="stat-num">{users.filter((u) => u.role === "part_labeler").length}</span> Part Labelers
          </div>
        </div>
      )}

      {/* Users table */}
      <div className="admin-table-wrap">
        {loading ? (
          <div className="admin-loading">Loading users…</div>
        ) : (
          <table className="admin-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Username</th>
                <th>Full Name</th>
                <th>Email</th>
                <th>Role</th>
                <th>Joined</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u, idx) => (
                <tr key={u.user_id} className={u.user_id === currentUserId ? "row-self" : ""}>
                  <td className="td-num">{idx + 1}</td>
                  <td className="td-username">{u.username}</td>
                  <td>{u.first_name} {u.last_name}</td>
                  <td className="td-email">{u.email}</td>
                  <td>
                    <span className={roleBadgeClass(u.role)}>{u.role}</span>
                  </td>
                  <td className="td-date">
                    {u.created_at ? u.created_at.slice(0, 10) : "—"}
                  </td>
                  <td className="td-actions">
                    {/* Role dropdown */}
                    <select
                      className="role-select"
                      value={u.role}
                      disabled={roleChanging[u.user_id] || u.user_id === currentUserId}
                      onChange={(e) => handleRoleChange(u.user_id, e.target.value)}
                      title={u.user_id === currentUserId ? "Cannot change your own role" : "Change role"}
                    >
                      {ROLES.map((r) => (
                        <option key={r} value={r}>{r}</option>
                      ))}
                    </select>

                    {/* Delete button */}
                    <button
                      className="delete-btn"
                      disabled={u.user_id === currentUserId}
                      title={u.user_id === currentUserId ? "Cannot delete your own account" : "Delete user"}
                      onClick={() => setConfirmDelete(u.user_id)}
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Delete confirmation modal */}
      {confirmDelete && (
        <div className="modal-overlay" onClick={() => setConfirmDelete(null)}>
          <div className="modal-box" onClick={(e) => e.stopPropagation()}>
            <h2>Confirm Delete</h2>
            <p>
              Are you sure you want to delete user{" "}
              <strong>{users.find((u) => u.user_id === confirmDelete)?.username}</strong>?
              This cannot be undone.
            </p>
            <div className="modal-actions">
              <button className="modal-cancel" onClick={() => setConfirmDelete(null)}>
                Cancel
              </button>
              <button className="modal-confirm" onClick={handleDeleteConfirm}>
                Yes, Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default AdminPanel;
