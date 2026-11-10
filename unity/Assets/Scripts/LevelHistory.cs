// LevelHistory.cs — a fixed-size rolling record of the feedback level for the HUD.
//
// One value per time bucket (default one second), oldest first. Gaps between
// samples carry the last value forward so the plotted curve has no holes, and a
// full record scrolls instead of growing. Plain C#, so it is unit-testable.

using System;

namespace MindX
{
    /// <summary>
    /// Rolling per-bucket history of a value with an optional flag per bucket.
    /// </summary>
    public sealed class LevelHistory
    {
        private readonly float[] _values;
        private readonly bool[] _flags;
        private readonly float _bucketSeconds;
        private int _count;
        private float _origin;

        /// <summary>
        /// Initializes a new instance of the <see cref="LevelHistory"/> class.
        /// </summary>
        /// <param name="capacity">Number of buckets kept.</param>
        /// <param name="bucketSeconds">Length of one bucket in seconds.</param>
        public LevelHistory(int capacity = 320, float bucketSeconds = 1f)
        {
            if (capacity < 1)
            {
                throw new ArgumentOutOfRangeException(nameof(capacity));
            }

            if (bucketSeconds <= 0f)
            {
                throw new ArgumentOutOfRangeException(nameof(bucketSeconds));
            }

            _values = new float[capacity];
            _flags = new bool[capacity];
            _bucketSeconds = bucketSeconds;
        }

        /// <summary>
        /// Gets the number of filled buckets.
        /// </summary>
        public int Count => _count;

        /// <summary>
        /// Gets the maximum number of buckets.
        /// </summary>
        public int Capacity => _values.Length;

        /// <summary>
        /// Gets the value of a bucket, oldest first.
        /// </summary>
        /// <param name="index">Bucket index in [0, Count).</param>
        /// <returns>The recorded value.</returns>
        public float this[int index] => _values[index];

        /// <summary>
        /// Gets the flag of a bucket, oldest first.
        /// </summary>
        /// <param name="index">Bucket index in [0, Count).</param>
        /// <returns>The flag recorded with the bucket's latest value.</returns>
        public bool Flag(int index) => _flags[index];

        /// <summary>
        /// Records a value; the latest value within a bucket wins.
        /// </summary>
        /// <param name="time">Time in seconds (monotonic).</param>
        /// <param name="value">The value to record.</param>
        /// <param name="flag">An optional marker stored with the bucket.</param>
        public void Record(float time, float value, bool flag = false)
        {
            if (_count == 0)
            {
                _origin = time;
            }

            int index = (int)Math.Floor((time - _origin) / _bucketSeconds);
            if (index < 0)
            {
                return;
            }

            if (index >= _values.Length)
            {
                int shift = index - _values.Length + 1;
                if (shift >= _values.Length)
                {
                    // A gap longer than the whole record: start again.
                    _count = 0;
                    _origin = time;
                    index = 0;
                }
                else
                {
                    Array.Copy(_values, shift, _values, 0, _values.Length - shift);
                    Array.Copy(_flags, shift, _flags, 0, _flags.Length - shift);
                    _count = Math.Max(0, _count - shift);
                    _origin += shift * _bucketSeconds;
                    index -= shift;
                }
            }

            float carry = _count > 0 ? _values[_count - 1] : value;
            bool carryFlag = _count > 0 ? _flags[_count - 1] : flag;
            for (int i = _count; i < index; i++)
            {
                _values[i] = carry;
                _flags[i] = carryFlag;
            }

            _values[index] = value;
            _flags[index] = flag;
            _count = Math.Max(_count, index + 1);
        }
    }
}
